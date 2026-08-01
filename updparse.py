#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#also this code dose not work at all because idk the tcp / udp that the server is send ing todo find the protocal that the server is useing
# Author:      Vincent A forked by lol you want my name 
# Description: Library to talk to an YSFlight server
# Usage:       Modify the classes Server and Apps to your needs 
#
# The following is a patched, ready-to-run version of the script you provided.
# It preserves the original behavior (map, weather, user list, air display options)
# and adds:
#  - robust receive() that reads the full payload
#  - a telemetry (aircraft state) parser for player location (type 11)
#  - consistent little-endian struct unpacking
#
# From the uploaded file: "Class doing the job of communicating with the server,
# using the two serialization classes: YS_proto_snd and YS_proto_rcv"

# `struct` encodes/decodes binary fields. `socket`, `json`, `logging`, and `time` handle networking, output, logging, and timing.
from struct import pack, unpack
import sys, socket, json, logging, time

# `YS_proto_snd` builds outbound server packets with a 32-bit length header followed by the payload.
class YS_proto_snd:
    """Serialization class: each method return the serialized data
    (the packet) to send data to the YSFlight server"""
    def snd(self, buffer):
        """Add to a packet the 'size' information."""
        # The protocol header is a little-endian unsigned 32-bit integer for the payload size.
        return pack("<I", len(buffer)) + buffer

    def reply(self, type, buffer):
        """
        Shortcut to reply to a packet that was received.
        The server usually expects a packet that echoes the same packet type back.
        """
        # The reply re-wraps the payload with the same packet type and adds the frame length header.
        return self.snd(pack("<I", type) + buffer)

    def ack(self, id, info):
        """
        Shortcut to send an acknowledgement packet.
        The original protocol uses a fixed packet shape: size, type, id, info.
        """
        # `12` is the fixed frame size, `6` is the acknowledgement type, and `id`/`info` confirm the request.
        return pack('<IIII', 12, 6, id, info)

    def login(self, username="test_user", version=20110207):
        """
        Returns a packet of type 1: login.
        We keep the existing character limit and packet layout expected by the server.
        """
        # The username is truncated to 16 bytes so it fits the fixed-width server field.
        username = username[0:15].encode('utf-8')
        # `version` is coerced to an integer for the protocol's numeric net-version field.
        version = int(version)
        # Packet layout: frame length, packet type 1, 16-byte username, and the version integer.
        return self.snd(pack("<I16sI", 1, username, version))

    def oneint(self, integer):
        # A one-int packet is a request payload for asking the server for a specific packet type.
        return self.snd(pack("<I", int(integer)))


# `YS_proto_rcv` turns server payload bytes back into Python values using fixed little-endian layouts.
class YS_proto_rcv:
    """Deserialization class: each method returns the information
    extracted from the serialized data in 'buffer'."""
    def airDisplayOpt(self, buffer):
        """
        Read packet of type 43.
        The packet contains a 32-bit integer prefix and then a printable ASCII option string.
        """
        # The format is a 32-bit integer prefix followed by the remaining byte string.
        decode = "<I{}s".format(len(buffer) - 4)
        return unpack(decode, buffer)

    def map(self, buffer):
        """
        Read packet of type 4.
        The server sends the map name in a fixed 60-byte string field.
        """
        return unpack("<60s", buffer)

    def msg(self, buffer):
        """
        Read packet of type 32.
        It contains a 32-bit signed integer marker followed by a chat-text byte string.
        """
        # `l` reads a signed long integer, and the remaining bytes are the message content.
        decode = "<l{}s".format(len(buffer) - 4)
        return unpack(decode, buffer)

    def oneint(self, buffer):
        """
        Read packet of type 29, 31, 39 or any single-int payload.
        This kind of packet uses only one unsigned integer field.
        """
        return unpack("<I", buffer)

    def userList(self, buffer):
        """
        Read packet of type 37.
        The payload contains two 16-bit values, two 32-bit values, and then a nickname string.
        """
        # Layout: two 16-bit fields, two 32-bit fields, then a trailing nickname byte string.
        decode = "<hhII{}s".format(len(buffer) - 12)
        return unpack(decode, buffer)

    def weather(self, buffer):
        """
        Read packet of type 33.
        The weather packet carries the day number, option bits, and three wind floats plus visibility.
        """
        return unpack("<IIffff", buffer)

    def aircraft_state(self, buffer):
        """
        Parse telemetry / aircraft state packet (commonly type 11).
        It returns the player ID and the six float coordinates/orientation values.
        """
        # The parser needs 1 unsigned int and 6 float fields, which is 28 bytes total.
        needed = 4 + 6 * 4
        if len(buffer) < needed:
            raise ValueError("buffer too short for aircraft_state")
        fmt = "<I6f"
        return unpack(fmt, buffer[:needed])


# `Server` stores the latest state seen from the game server as the packet loop updates it.
class Server:
    """Class to store all the information we got from our communication
    with the YSFlight server."""
    def __init__(self, ip, port):
        # The connection endpoint is remembered for debugging and diagnostics.
        self.ip         = ip
        self.port       = port
        # `version` tracks the server's reported protocol version.
        self.version    = 20110207
        # `status` starts as offline until the socket successfully connects.
        self.status     = "offline"
        # `map` stores the latest map string returned by the server.
        self.map        = ""
        # Boolean-like flags show whether missile, weapon, blackout, collision, or landing events are enabled.
        self.missileON  = 0
        self.weaponON   = 0
        self.blackoutON = 0
        self.collON     = 0
        self.landevON   = 0
        # Weather is stored as day, option bits, wind x/y/z, and visibility.
        self.weather    = (0,0,0.0,0.0,0.0,0.0)
        # `userOption` stores the UI display preference value from packet type 41.
        self.userOption = 0  # Show User Name within 'userOption' m
        # `radarAlti` stores the parsed radar altitude value.
        self.radarAlti  = ""
        # `f3view` tracks whether the server reports the F3 view option.
        self.f3view     = True
        # `userList` stores the parsed user-list tuples.
        self.userList   = []
        # `users` and `flyingUsers` count the distinct and airborne users seen in the response.
        self.users      = 0
        self.flyingUsers= 0
        # `positions` maps player IDs to the most recent position snapshot for that player.
        self.positions  = {}  # pid -> last known position dict


# `Apps` owns the socket, packet encoder/decoder, and the dispatch loop that updates server state.
class Apps:
    """Class doing the job of communicating with the server,
    using the two serialization classes: YS_proto_snd and YS_proto_rcv.
    """
    def __init__(self, ip, port, timeout):
        # The endpoint and timeout are saved for every socket operation.
        self.ip       = ip
        self.port     = port
        # `server` caches the latest game information received from the remote host.
        self.server   = Server(ip, port)
        # `ysrcv` and `yssnd` convert payload bytes and craft outbound frames.
        self.ysrcv    = YS_proto_rcv()
        self.yssnd    = YS_proto_snd()
        # `packets` counts processed packets so the loop can stop after a fixed number.
        self.packets  = 0
        # `version` stores the client-side protocol version expectation.
        self.version  = 0
        self.timeout  = timeout
        # `username` is used in login and reconnect logic.
        self.username = ''
        # `connected` is only true after a successful TCP connection is made.
        self.connected = False
        # `s` holds the live network socket instance.
        self.s = None

    def connect(self, username, version):
        """
        Start the connection and the main loop of discussion with the server.
        The connection flow is: create the socket, open the TCP connection,
        send a protocol login packet, then continuously receive and parse packets.
        """
        # A fresh TCP socket is created for every connection attempt.
        self.s        = socket.socket()
        # The socket timeout prevents the client from blocking forever on reads or writes.
        self.s.settimeout(self.timeout)
        # Store the username and version the client is currently using for this session.
        self.version  = version
        self.username = username
        # We only mark the client as connected after `connect()` succeeds.
        self.connected = False
        try:
            # Open the TCP stream to the game server.
            self.s.connect((self.ip, self.port))
            self.connected = True
        except Exception:
            # If the network handshake fails, the server is considered offline.
            self.server.status = "offline"
            logger.info("connect failed")
            return
        # Send the structured login packet that identifies this client to the server.
        if not(self.send(self.yssnd.login(username, version))):
            # If the initial login write fails, the server is effectively locked against us.
            self.server.status = "locked"
            return
        logger.info("connected")
        # The outer loop is the protocol session loop: repeatedly read one packet, dispatch it,
        # and continue until the socket is closed or the packet limit is reached.
        while self.connected and self.packets < 1000:
            # Receive one network frame. The returned tuple is (`size`, `type`, `buffer`).
            (size, type, buffer) = self.receive()
            if size == 0 and type == 0:
                # A zero-size/zero-type read means the socket either died or the read failed.
                logger.info("receive returned empty, disconnecting")
                self.disconnect()
                break
            # Every valid packet we read increments the packet progress counter.
            self.packets += 1
            self.server.status = "online"
            # `process()` decides what this packet means and updates the server state accordingly.
            if not(self.process(size, type, buffer)):
                # A false return means the packet processing did not produce a useful state transition.
                # We keep the server noted as online, but do not treat it as a fatal error.
                self.server.status = "online"
            # A tiny sleep keeps the event loop from spinning too aggressively when many packets arrive rapidly.
            time.sleep(0.001)

    def disconnect(self):
        # Disconnect means the loop should stop reading from the network and the socket should be closed.
        self.connected = False
        try:
            if self.s:
                self.s.close()
        except Exception:
            logger.info("failed to disconnect")

    def send(self, buffer):
        """Send `buffer` to the server and report success or failure.
        For protocol requests, this function wraps the network write and surfaces any exception.
        """
        try:
            # A complete serialized packet is sent directly as a byte string.
            self.s.send(buffer)
            return 1
        except Exception as e:
            logger.info("Send failure: " + str(e))
            return 0

    def receive(self):
        """Receive a complete frame from the server and return `(size, type, buffer)`.
        The frame layout is `[size:uint32][type:uint32][payload bytes]`.
        """
        try:
            # First read the length header, which tells us how many bytes belong to the rest of the packet.
            raw = self.s.recv(4)
            if len(raw) < 4:
                logger.debug("Receive failure: header size short")
                return (0, 0, "")
            size = self.ysrcv.oneint(raw)[0]

            # Next read the packet type field so we know how to interpret the payload.
            raw = self.s.recv(4)
            if len(raw) < 4:
                logger.debug("Receive failure: header type short")
                return (0, 0, "")
            type = self.ysrcv.oneint(raw)[0]
            logger.debug("size %d type %d", size, type)
        except Exception as e:
            # Any exception here usually means the socket is broken or timed out.
            logger.debug("Receive failure 1: %s", str(e))
            return (0, 0, "")

        # The remainder of the frame after the 4-byte type field is the payload.
        # We keep reading until the payload length is fully satisfied.
        to_read = size - 4
        buf = b''
        while to_read > 0:
            try:
                chunk = self.s.recv(to_read)
                if not chunk:
                    # The server closed the connection without sending a complete payload.
                    break
                buf += chunk
                to_read -= len(chunk)
            except Exception as e:
                logger.debug("Receive failure 2: %s", str(e))
                break
        return (size, type, buf)

    def process(self, size, type, buffer):
        """
        Route a received packet to the correct parser based on its packet type.
        The general pattern is: decode bytes -> update the server state -> optionally acknowledge.
        """
        # A zero packet type is treated as an invalid or terminal packet and is not processed.
        if type == 0:
            return 0
        elif type == 4:
            # Packet type 4 carries the map name. The map name is stored as a fixed-width bytes string.
            raw_map = self.ysrcv.map(buffer)[0]
            # Remove the trailing NUL padding that comes with many fixed-width server strings.
            end = raw_map.find(b'\x00')
            if end != -1:
                raw_map = raw_map[:end]
            try:
                # Decode the remaining bytes into UTF-8 text so humans can read the map name.
                self.server.map = raw_map.decode('utf-8', errors='ignore')
            except Exception:
                # If decoding fails, keep the low-level bytes representation instead of crashing.
                self.server.map = str(raw_map)
            logger.info("map %s", self.server.map)
            # Echo the map packet back to show that we have read it and are still talking to the server.
            self.send(self.yssnd.reply(4, buffer))
            # Once the map is known, request the weather and user list packets as follow-up data.
            self.send(self.yssnd.oneint(33))
            self.send(self.yssnd.oneint(37))
        elif type == 11:
            print("DEBUG: aircraft payload len =", len(buffer))
            print("DEBUG: aircraft payload hex =", buffer.hex())

            # Packet type 11 is aircraft telemetry: a player state snapshot with world position and orientation.
            try:
                pid, x, y, z, heading, pitch, bank = self.ysrcv.aircraft_state(buffer)
                logger.info("Player %d pos x=%.2f y=%.2f z=%.2f hdg=%.2f pitch=%.2f bank=%.2f",
                            pid, x, y, z, heading, pitch, bank)
                # Cache the last known world position for this player ID, using the current time as a timestamp.
                self.server.positions[pid] = {
                    'x': x, 'y': y, 'z': z,
                    'heading': heading, 'pitch': pitch, 'bank': bank,
                    'ts': time.time()
                }
            except Exception as e:
                logger.debug("Failed to parse aircraft_state: %s", str(e))
        elif type == 16:
            # Type 16 indicates the air-list phase has completed, so an acknowledgement is sent.
            self.send(self.yssnd.ack(7, 0))
        elif type == 29:
            # Packet type 29 carries the server's reported net version.
            self.server.version = self.ysrcv.oneint(buffer)[0]
            logger.info("version %d", self.server.version)
            if self.version != self.server.version:
                # If the server speaks a different version, the client should reconnect with the server's version.
                logger.warning("reconnecting with another net-version")
                self.disconnect()
                # A short pause avoids reconnecting in a tight loop immediately after version mismatch.
                time.sleep(0.5)
                self.connect(self.username, self.server.version)
            else:
                # In the matching-version case, acknowledge the server's version packet.
                self.send(self.yssnd.ack(9, 0))
        elif type == 31:
            # Packet type 31 reports whether missiles are enabled or disabled.
            self.server.missileON = bool(self.ysrcv.oneint(buffer)[0])
            logger.info("missileON %s", str(self.server.missileON))
            self.send(self.yssnd.ack(10, 0))
        elif type == 32:
            # Type 32 is a chat or textual message packet.
            msg = self.ysrcv.msg(buffer)[1].decode('utf-8', errors='ignore')
            logger.info("message %s", msg)
            # Messages do not advance the meaningful game-state progress, so they should not count as progress.
            self.packets -= 1
        elif type == 33:
            # Packet type 33 delivers the weather block: day, option bits, wind vectors, visibility.
            self.server.weather = self.ysrcv.weather(buffer)
            opts = bin(self.server.weather[1])
            opts_str = str(opts)
            # The option bits are interpreted from the rightmost positions of the binary string.
            # Specifically, each flag is a single bit in the server-provided option mask.
            if len(opts_str) > 5:
                self.server.collON = bool(int(opts_str[-5]))
            else:
                self.server.collON = False
            if len(opts_str) > 7:
                self.server.blackoutON = bool(int(opts_str[-7]))
            else:
                self.server.blackoutON = False
            if len(opts_str) > 3:
                self.server.landevON = bool(int(opts_str[-3]))
            else:
                self.server.landevON = False
            logger.info("collON %s", str(self.server.collON))
            logger.info("blackoutON %s", str(self.server.blackoutON))
            logger.info("landevON %s", str(self.server.landevON))
            logger.info(
                "day %s windX %s windY %s windZ %s visib %s" %
                (str(self.server.weather[0]),
                 str(self.server.weather[2]),
                 str(self.server.weather[3]),
                 str(self.server.weather[4]),
                 str(self.server.weather[5]))
            )
            # Once the weather information has been consumed, acknowledge the request.
            self.send(self.yssnd.ack(4, 0))
        elif type == 37:
            # Packet type 37 is a user-list entry. The server can send many of these entries.
            try:
                user = list(self.ysrcv.userList(buffer))
                # `user[4]` is the nickname in bytes form.
                nick_bytes = user[4]
                nick_bytes = nick_bytes.rstrip(b'\0')
                nickname = nick_bytes.decode('utf-8', errors='ignore')
                user[4] = nickname
                user = tuple(user)
                # Store each parsed entry in the server's user list buffer.
                self.server.userList.append(user)
                if user[0] == 1 or user[0] == 3:
                    self.server.flyingUsers += 1
                if user[4] != self.username and user[4] != 'Console Server':
                    self.server.users += 1
                logger.info("user %s", str(user))
            except Exception as e:
                logger.debug("Failed to parse userList: %s", str(e))
        elif type == 39:
            # Packet type 39 reports whether weapons are enabled.
            self.server.weaponON = bool(self.ysrcv.oneint(buffer)[0])
            logger.info("weaponON %s", str(self.server.weaponON))
            self.send(self.yssnd.ack(11, 0))
        elif type == 41:
            # Packet type 41 carries a single option value for the user interface.
            self.server.userOption = self.ysrcv.oneint(buffer)[0]
            logger.info("User option %s", str(self.server.userOption))
        elif type == 43:
            # Packet type 43 contains air-display options, such as F3 view/radar altitude status.
            self.send(self.yssnd.reply(43, buffer))
            mesg = self.ysrcv.airDisplayOpt(buffer)[1]
            if mesg[:14] == b"NOEXAIRVW TRUE":
                # The server is explicitly telling us that the F3 view is disabled.
                logger.info("no F3 view")
                self.server.f3view = False
            else:
                try:
                    # Some server variants embed the radar altitude as ASCII text inside the buffer.
                    self.server.radarAlti = float(mesg[10:-2])
                except Exception:
                    # If parsing that text fails, fall back to a neutral zero value rather than crash.
                    self.server.radarAlti = 0
                logger.info("radar alti %s", str(self.server.radarAlti))
        elif type == 44:
            # Type 44 is an aircraft list packet; the client replies to acknowledge receipt.
            self.send(self.yssnd.reply(44, buffer))
        else:
            # Unsupported packet types are ignored but logged so the protocol can be extended safely.
            logger.debug("Unhandled packet type %d (size %d)", type, size)
        return 1


if __name__ == '__main__':
    # This script entry point is the small command-line harness used to test the protocol client.
    # The command line is: `python3 updparse.py <ip> <port> [username] [net_version]`.
    logger = logging.getLogger('ys_proto')
    hdlr = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)

    # A minimal command-line argument check: server IP and port are mandatory.
    if len(sys.argv) < 3:
        print("Usage: {} <server_ip> <server_port> [username] [net_version]".format(sys.argv[0]))
        sys.exit(1)

    # Parse the two required CLI values and optional username/version overrides.
    ip = sys.argv[1]
    port = int(sys.argv[2])
    username = sys.argv[3] if len(sys.argv) > 3 else "serverlist_bot"
    net_version = int(sys.argv[4]) if len(sys.argv) > 4 else 20150425

    # Build the client object and connect to the server using the selected transport timeout.
    apps = Apps(ip, port, 5)
    try:
        apps.connect(username, net_version)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Emit a compact JSON-style summary of the server snapshot when the process exits.
        try:
            # Convert numeric keys in the position cache into strings so they can be serialized cleanly.
            positions = {str(k): v for k, v in apps.server.positions.items()}
            out = vars(apps.server).copy()
            out['positions'] = positions
            # The raw socket object is not JSON-serializable, so it is removed from the output.
            out.pop('ip', None)
            print(json.dumps({
                'map': apps.server.map,
                'version': apps.server.version,
                'users': apps.server.users,
                'flyingUsers': apps.server.flyingUsers,
                'weather': apps.server.weather,
                'f3view': apps.server.f3view,
                'radarAlti': apps.server.radarAlti,
                'positions': positions
            }, default=str, indent=2))
        except Exception:
            pass
