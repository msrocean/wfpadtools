"""
The wfpad module implements the Tor WF framework to develop WF countermeasures.
"""
from obfsproxy.transports.base import BaseTransport, PluggableTransportError
from obfsproxy.transports.scramblesuit import probdist
from obfsproxy.transports.scramblesuit.fifobuf import Buffer
from obfsproxy.transports.wfpadtools import message
from twisted.internet import reactor

import obfsproxy.common.log as logging
import obfsproxy.transports.wfpadtools.const as const
from obfsproxy.transports.wfpadtools.message import WFPadMessage


log = logging.get_obfslogger()


class WFPadTransport(BaseTransport):
    """Implements the Tor WF framework to develop WF countermeasures.

    This class implements methods which implement primitives and protocols
    specifications to further develop WF countermeasures.
    """
    def __init__(self):
        """Initialize a WFPadTransport object."""
        log.debug("Initializing %s." % const.TRANSPORT_NAME)

        super(WFPadTransport, self).__init__()

        # Initialize the protocol's state machine.
        self._state = const.ST_WAIT

        # Buffer for outgoing data.
        self.sendBuf = ""

        # Count time spent on padding
        self.elapsed = 0

        # Buffer used for padding.
        self.padding_buffer = Buffer()

        # Counter for padding messages
        self.num_padding_msgs = 0

        # Used to extract protocol messages from encrypted data.
        self.msg_factory = message.WFPadMessageFactory()
        self.msg_extractor = message.WFPadMessageExtractor()

    @classmethod
    def setup(cls, transportConfig):
        """Called once when obfsproxy starts."""
        log.error("\n\n"
                  "########################################################\n"
                  " WFPad isn't a Website Fingerprinting defense by itself.\n"
                  "########################################################\n")

        cls.weAreClient = transportConfig.weAreClient
        cls.weAreServer = not cls.weAreClient
        cls.weAreExternal = transportConfig.weAreExternal

    @classmethod
    def register_external_mode_cli(cls, subparser):
        """Register CLI arguments."""
        subparser.add_argument("--period",
                               required=False,
                               type=float,
                               help="Time rate at which transport sends "
                                    "messages (Default: 1ms).",
                               dest="period")
        subparser.add_argument("--psize",
                               required=False,
                               type=int,
                               help="Length of messages to be transmitted"
                                    " (Default: MTU).",
                               dest="psize")
        super(WFPadTransport, cls).register_external_mode_cli(subparser)

    @classmethod
    def validate_external_mode_cli(cls, args):
        """Assign the given command line arguments to local variables.

        Initializes the probability distributions used by WFPad.
        """
        # Defaults for WFPad parameters.
        period = 0.001
        psize = const.MTU

        if args.period:
            period = args.period
        if args.psize:
            psize = args.psize

        parentalApproval = super(
            WFPadTransport, cls).validate_external_mode_cli(args)
        if not parentalApproval:
            raise PluggableTransportError(
                "Pluggable Transport args invalid: %s" % args)

        # Initialize probability distributions used by WFPad.
        cls._delay_probdist = probdist.new(lambda: period)
        cls._length_probdist = probdist.new(lambda: psize)

    def circuitConnected(self):
        """Initiate handshake.

        This method is only relevant for clients since servers never initiate
        handshakes.
        """
        # Start padding link
        self.flushSendBuffer()
        self._state = const.ST_CONNECTED
        self.start_padding()

    def sendRemote(self, data, flags=const.FLAG_DATA):
        """Send data to the remote end once the connection is established.

        The given `data` is first encapsulated in protocol messages.  Then, the
        protocol message(s) are sent over the wire.  The argument `flags'
        specifies the protocol message flags.
        """
        log.debug("Processing %d bytes of outgoing data." % len(data))
        if self._state is const.ST_PADDING:
            self.padding_buffer.write(data)

    def flushPieces(self):
        """Write the application data in chunks to the wire.

        In case the buffer is not empty, the buffer is flushed and we send
        these data over the wire. Otherwise, we generate random padding
        and we send it over the wire in chunks. After every write call,
        control is given back to the Twisted reactor. The function is called
        again after a certain delay, which is sampled from the time
        probability distribution.
        """
        if self.stop_condition():
            self.stop_padding()
            return

        msg = WFPadMessage()
        msg_total_len = self.get_msg_length()
        payload_len = msg_total_len - const.HDR_LENGTH
        data_len = len(self.padding_buffer)
        if data_len > 0:
            log.debug("Flush buffer")
            if data_len > payload_len:
                log.debug("Message with no padding.")
                data = self.padding_buffer.read(payload_len)
                msg = self.msg_factory.createWFPadMessage(data)
            else:
                log.debug("Message with padding.")
                data = self.padding_buffer.read()
                padding_len = payload_len - data_len
                msg = self.msg_factory.createWFPadMessage(data,
                                                    padding_len)
        else:
            log.debug("Generate padding")
			self.num_padding_msgs += 1
            msg = self.msg_factory.createWFPadMessage("", payload_len,
                                                      flags=const.FLAG_PADDING)
        self.circuit.downstream.write(str(msg))

        delay = self.get_flush_delay()
        self.elapsed += delay
        reactor.callLater(delay, self.flushPieces)

    def get_msg_length(self):
        """Return length for a specific message.

        The final countermeasure could override this method to,
        instead of drawing the delay from a probability distribution,
        iterate over a list to mimic a specific pattern of lengths.
        """
        return self._length_probdist.randomSample()

    def get_flush_delay(self):
        """Return delay between calls to `flushPieces`.

        The final countermeasure could override this method to,
        instead of drawing the delay from a probability distribution,
        iterate over a list to mimic a specific pattern of delays.
        """
        return self._delay_probdist.randomSample()

    def processMessages(self, data):
        """Acts on extracted protocol messages based on header flags.

        Data is written to the local application and padding messages are
        filtered out from the stream.
        """
        log.debug("I'm going to parse protocol messages from data.")
        if (data is None) or (len(data) == 0):
            return

        # Try to extract protocol messages.
        msgs = self.msg_extractor.extract(data)
        for msg in msgs:
            if (msgs is None) or (len(msgs) == 0):
                return
            for msg in msgs:
                # Forward data to the application.
                if msg.flags == const.FLAG_DATA:
                    log.debug("Fata flag detected, relaying tor data stream")
                    self.circuit.upstream.write(msg.payload)

                # Filter padding messages out.
                elif msg.flags == const.FLAG_PADDING:
                    log.debug("Padding message ignored.")
                else:
                    log.warning("Invalid message flags: %d." % msg.flags)

    def get_num_padding_msgs(self):
        """Return number of padding messages."""
        return self.num_padding_msgs

    def get_elapsed(self):
        """Return time elapsed since padding started."""
        return self.elapsed

    def start_padding(self):
        """Changes protocol's state to ST_PADDING and starts timer."""
        self._state = const.ST_PADDING
        self.elapsed = 0
        self.flushPieces()

    def stop_padding(self):
        """Changes protocol's state to ST_CONNECTED and stops timer."""
        self._state = const.ST_CONNECTED
        self.flushPieces()

    def stop_condition(self):
        """Return the evaluation of the stop condition.

        We assume that the most general scheme is to be continuously padding.
        More sophisticated defenses try to reduce the overhead and set a
        stopping condition.
        """
        return False

    def flushSendBuffer(self):
        """Flush the application's queued data.

        The application could have sent data while we were busy authenticating
        the remote machine.  This method flushes the data which could have been
        queued in the meanwhile in `self.sendBuf'.
        """
        if len(self.sendBuf) == 0:
            log.debug("Send buffer is empty; nothing to flush.")
            return

        # Flush the buffered data, the application is so eager to send.
        log.debug("Flushing %d bytes of buffered application data." %
                  len(self.sendBuf))

        self.sendRemote(self.sendBuf)
        self.sendBuf = ""

    def run_before_flushing(self):
        """Perform the following operations before flushing the buffer.

        This method is called at the beginning of the flushPieces method. It
        might be used to eventually change the probability distributions used
        for sampling lengths and delays. An edge case could be to change the
        length and delay for each individual message to mimick some predefined
        traffic template.
        """
        pass

    def receivedUpstream(self, data):
        """Got data from upstream; relay them downstream."""
        if self._state == const.ST_PADDING:
            self.sendRemote(data.read())
        else:
            self.sendBuf += data.read()
            log.debug("Buffered %d bytes of outgoing data." %
                      len(self.sendBuf))

    def receivedDownstream(self, data):
        """Got data from downstream; relay them upstream."""
        if self._state is const.ST_PADDING:
            self.processMessages(data.read())
        else:
            self.flushSendBuffer()


class WFPadClient(WFPadTransport):
    """Extend the WFPad class."""

    def __init__(self):
        """Initialize a WFPadClient object."""
        WFPadTransport.__init__(self)


class WFPadServer(WFPadTransport):
    """Extend the WFPad class."""

    def __init__(self):
        """Initialize a WFPadServer object."""
        WFPadTransport.__init__(self)
