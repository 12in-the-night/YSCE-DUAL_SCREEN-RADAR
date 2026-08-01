#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Author:      Vincent A
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

from struct import pack, unpack
import sys, socket, json, logging, time

class YS_proto_snd:
    """Serialization class: each method return the serialized data
    (the packet) to send data to the YSFlight server"""
    def snd(self, buffer):
        """Add to a packet the 'size' information"""
        return pack("<I", len(buffer)) + buffer

    def reply(self, type, buffer):
        """
        Shortcut to reply the packet you received
        @type int: the type of the received packet
        @type char[]: the received buffer
        @return: the reply
        """
        return self.snd(pack("<I", type) + buffer)

    def ack(self, id, info):
        """
        Shortcut to send an acknowledgement packet
        This returns a full packet (size + type + id + info) as in original script.
        """
        return pack('<IIII', 12, 6, id, info)

    def login(self, username="test_user", version=20110207):
        """
        Returns a packet of type 1: login
        @type str: username
        @type int: YS net-version
        @return: The login packet
        """
        username = username[0:15].encode('utf-8')
        version = int(version)
        # pack type (1) + username (16 bytes) + version
        return self.snd(pack("<I16sI", 1, username, version))

    def oneint(self, integer):
        # returns a packet containing a single int payload (used to request other packets)
        return self.snd(pack("<I", int(integer)))


class YS_proto_rcv:
    """Deserialization class: each method returns the information
    extracted from the serialized data in 'buffer'"""
    def airDisplayOpt(self, buffer):
        """
        Read packet of type 43
        @type byte[]: buffer
        @return: The tuple (unknown, option_string)
        """
        decode = "<I{}s".format(len(buffer) - 4)
        return unpack(decode, buffer)

    def map(self, buffer):
        """
        Read packet of type 4
        @type bytes: buffer
        @return: A tuple containing the name of the map (bytes)
        """
        return unpack("<60s", buffer)

    def msg(self, buffer):
        """
        Read packet of type 32
        @type bytes: buffer
        @return: The tuple (unknown_long, chat_message)
        """
        decode = "<l{}s".format(len(buffer) - 4)
        return unpack(decode, buffer)

    def oneint(self, buffer):
        """
        Read packet of type 29, 31, 39 or any single-int payload
        @type bytes: buffer
        @return: tuple with one unsigned int
        """
        return unpack("<I", buffer)

    def userList(self, buffer):
        """
        Read packet of type 37
        @type bytes: buffer
        @return: The tuple (action(short), IFF(short), ID(uint32), unknown(uint32), nickname(bytes))
        """
        decode = "<hhII{}s".format(len(buffer) - 12)
        return unpack(decode, buffer)

    def weather(self, buffer):
        """
        Read packet of type 33
        @type bytes: buffer
        @return: The tuple (day:uint32, options:uint32, windX:float, windY:float, windZ:float, visib:float)
        """
        return unpack("<IIffff", buffer)

    def aircraft_state(self, buffer):
        """
        Parse telemetry / aircraft state packet (commonly type 11).
        Returns tuple: (id:uint32, x:float, y:float, z:float, heading:float, pitch:float, bank:float, ...)
        This unpacks the first 1 uint32 + 6 floats (28 bytes). If the packet is longer,
        only the first fields are returned here; you can extend the format if needed.
        """
        needed = 4 + 6 * 4  # id + 6 floats
        if len(buffer) < needed:
            raise ValueError("buffer too short for aircraft_state")
        fmt = "<I6f"
        return unpack(fmt, buffer[:needed])


class Server:
    """Class to store all the information we got from our communication
    with the YSFlight server."""
    def __init__(self, ip, port):
        self.ip         = ip
        self.port       = port
        self.version    = 20110207
        self.status     = "offline"
        self.map        = ""
        self.missileON  = 0
        self.weaponON   = 0
        self.blackoutON = 0
        self.collON     = 0
        self.landevON   = 0
        self.weather    = (0,0,0.0,0.0,0.0,0.0)
        self.userOption = 0 # Show User Name within 'userOption' m
        self.radarAlti  = ""
        self.f3view     = True
        self.userList   = []
        self.users      = 0
        self.flyingUsers= 0
        self.positions  = {}  # pid -> last known position dict


class Apps:
    """Class doing the job of communicating with the server,
    using the two serialization classes: YS_proto_snd and YS_proto_rcv
    """
    def __init__(self, ip, port, timeout):
        self.ip       = ip
        self.port     = port
        self.server   = Server(ip, port)
        self.ysrcv    = YS_proto_rcv()
        self.yssnd    = YS_proto_snd()
        self.packets  = 0
        self.version  = 0
        self.timeout  = timeout
        self.username = ''
        self.connected = False
        self.s = None

    def connect(self, username, version):
        """
        Start the connection and the main loop of discussion
        with the server.
        @type string: username is the nickname used for the login
        @type string: version is the net-version used for the login
        @return string: the state of the server ('online', ...)
        """
        self.s        = socket.socket()
        self.s.settimeout(self.timeout)
        self.version  = version
        self.username = username
        self.connected = False
        try:
            self.s.connect((self.ip, self.port))
            self.connected = True
        except Exception:
            self.server.status = "offline"
            logger.info("connect failed")
            return
        if not(self.send(self.yssnd.login(username, version))):
            self.server.status = "locked"
            return
        logger.info("connected")
        # main loop: read packets until disconnected or packet limit reached
        while self.connected and self.packets < 1000:
            (size, type, buffer) = self.receive()
            if size == 0 and type == 0:
                # receive failure or closed socket
                logger.info("receive returned empty, disconnecting")
                self.disconnect()
                break
            self.packets += 1
            self.server.status = "online"
            if not(self.process(size, type, buffer)):
                # process returned false -> treat as lag or stop condition
                self.server.status = "online"
            # small sleep to avoid busy loop in case of immediate returns
            time.sleep(0.001)

    def disconnect(self):
        self.connected = False
        try:
            if self.s:
                self.s.close()
        except Exception:
            logger.info("failed to disconnect")

    def send(self, buffer):
        """Send 'buffer' to the server
        @return: 1 if success, 0 else
        """
        try:
            self.s.send(buffer)
            return 1
        except Exception as e:
            logger.info("Send failure: " + str(e))
            return 0

    def receive(self):
        """Receive data from the server and return (size, type, buffer)
        size=0 and type=0 in case of failure
        This implementation reads exactly the expected number of bytes for the payload.
        """
        try:
            raw = self.s.recv(4)
            if len(raw) < 4:
                logger.debug("Receive failure: header size short")
                return (0, 0, "")
            size = self.ysrcv.oneint(raw)[0]
            raw = self.s.recv(4)
            if len(raw) < 4:
                logger.debug("Receive failure: header type short")
                return (0, 0, "")
            type = self.ysrcv.oneint(raw)[0]
            logger.debug("size %d type %d", size, type)
        except Exception as e:
            logger.debug("Receive failure 1: %s", str(e))
            return (0, 0, "")

        # read exactly size-4 bytes for the payload
        to_read = size - 4
        buf = b''
        while to_read > 0:
            try:
                chunk = self.s.recv(to_read)
                if not chunk:
                    # socket closed
                    break
                buf += chunk
                to_read -= len(chunk)
            except Exception as e:
                logger.debug("Receive failure 2: %s", str(e))
                break
        return (size, type, buf)

    def process(self, size, type, buffer):
        """
        Takes the decision of what doing when we receive a packet of type X
        """
        if type == 0:
            return 0
        elif type == 4:
            # Map packet
            raw_map = self.ysrcv.map(buffer)[0]
            end = raw_map.find(b'\x00')
            if end != -1:
                raw_map = raw_map[:end]
            try:
                self.server.map = raw_map.decode('utf-8', errors='ignore')
            except Exception:
                self.server.map = str(raw_map)
            logger.info("map %s", self.server.map)
            # reply to server's map packet
            self.send(self.yssnd.reply(4, buffer))
            # ask to get the weather packet:
            self.send(self.yssnd.oneint(33))
            # ask to get the user-list:
            self.send(self.yssnd.oneint(37))
        elif type == 11:
            # Aircraft telemetry / state packet (player location)
            try:
                pid, x, y, z, heading, pitch, bank = self.ysrcv.aircraft_state(buffer)
                logger.info("Player %d pos x=%.2f y=%.2f z=%.2f hdg=%.2f pitch=%.2f bank=%.2f",
                            pid, x, y, z, heading, pitch, bank)
                # store last known position
                self.server.positions[pid] = {
                    'x': x, 'y': y, 'z': z,
                    'heading': heading, 'pitch': pitch, 'bank': bank,
                    'ts': time.time()
                }
            except Exception as e:
                logger.debug("Failed to parse aircraft_state: %s", str(e))
        elif type == 16:
            # we finished with the air-list
            self.send(self.yssnd.ack(7, 0))
        elif type == 29:
            self.server.version = self.ysrcv.oneint(buffer)[0]
            logger.info("version %d", self.server.version)
            if self.version != self.server.version:
                logger.warning("reconnecting with another net-version")
                # reconnect with server's version
                self.disconnect()
                # small delay before reconnect
                time.sleep(0.5)
                self.connect(self.username, self.server.version)
            else:
                self.send(self.yssnd.ack(9, 0))
        elif type == 31:
            self.server.missileON = bool(self.ysrcv.oneint(buffer)[0])
            logger.info("missileON %s", str(self.server.missileON))
            self.send(self.yssnd.ack(10, 0))
        elif type == 32:
            msg = self.ysrcv.msg(buffer)[1].decode('utf-8', errors='ignore')
            logger.info("message %s", msg)
            # A message from a server maybe player generated and does not
            # contribute to any in-game information, avoid incrementing
            # the packet count, as this is not progress.
            self.packets -= 1
        elif type == 33:
            self.server.weather = self.ysrcv.weather(buffer)
            opts = bin(self.server.weather[1])
            opts_str = str(opts)
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
            # acknowledge map/weather request
            self.send(self.yssnd.ack(4, 0))
        elif type == 37:
            # User list entry
            try:
                user = list(self.ysrcv.userList(buffer))
                # user[4] is bytes nickname
                nick_bytes = user[4]
                nick_bytes = nick_bytes.rstrip(b'\0')
                nickname = nick_bytes.decode('utf-8', errors='ignore')
                user[4] = nickname
                user = tuple(user)
                self.server.userList.append(user)
                if user[0] == 1 or user[0] == 3:
                    self.server.flyingUsers += 1
                if user[4] != self.username and user[4] != 'Console Server':
                    self.server.users += 1
                logger.info("user %s", str(user))
            except Exception as e:
                logger.debug("Failed to parse userList: %s", str(e))
        elif type == 39:
            self.server.weaponON = bool(self.ysrcv.oneint(buffer)[0])
            logger.info("weaponON %s", str(self.server.weaponON))
            self.send(self.yssnd.ack(11, 0))
        elif type == 41:
            self.server.userOption = self.ysrcv.oneint(buffer)[0]
            logger.info("User option %s", str(self.server.userOption))
        elif type == 43:
            # Air display options
            self.send(self.yssnd.reply(43, buffer))
            mesg = self.ysrcv.airDisplayOpt(buffer)[1]
            if mesg[:14] == b"NOEXAIRVW TRUE":
                logger.info("no F3 view")
                self.server.f3view = False
            else:
                try:
                    # message contains radar altitude as ascii in some servers
                    self.server.radarAlti = float(mesg[10:-2])
                except Exception:
                    self.server.radarAlti = 0
                logger.info("radar alti %s", str(self.server.radarAlti))
        elif type == 44:
            # aircraft list (server may send a list; reply to acknowledge)
            self.send(self.yssnd.reply(44, buffer))
        else:
            logger.debug("Unhandled packet type %d (size %d)", type, size)
        return 1


if __name__ == '__main__':
    # Basic CLI usage: python3 ys_proto_patched.py <ip> <port>
    logger = logging.getLogger('ys_proto')
    hdlr = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)

    if len(sys.argv) < 3:
        print("Usage: {} <server_ip> <server_port> [username] [net_version]".format(sys.argv[0]))
        sys.exit(1)

    ip = sys.argv[1]
    port = int(sys.argv[2])
    username = sys.argv[3] if len(sys.argv) > 3 else "serverlist_bot"
    net_version = int(sys.argv[4]) if len(sys.argv) > 4 else 20150425

    apps = Apps(ip, port, 5)
    try:
        apps.connect(username, net_version)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # print server state summary
        try:
            # convert positions to serializable form
            positions = {str(k): v for k, v in apps.server.positions.items()}
            out = vars(apps.server).copy()
            out['positions'] = positions
            # remove socket object if present
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
