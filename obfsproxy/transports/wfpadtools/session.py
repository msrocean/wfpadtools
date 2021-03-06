import time

from twisted.internet.defer import Deferred


class Session(object):
    """Contains state and variables for the current session.

    A session is defines as a visit to a web page.
    """

    def __init__(self):
        # Flag padding
        self.is_padding = False
        self.stop_padding = Deferred()

        # Statistics to keep track of past messages
        # Used for debugging
        self.history = []

        # Used for congestion sensitivity
        self.lastSndDownstreamTs = 0
        self.lastSndDataDownstreamTs = 0

        self.lastRcvDownstreamTs = 0
        self.lastRcvDataDownstreamTs = 0

        self.lastRcvUpstreamTs = 0
        self.consecPaddingMsgs = 0

        self.dataBytes = {'rcv': 0, 'snd': 0}
        self.totalBytes = {'rcv': 0, 'snd': 0}
        self.numMessages = {'rcv': 0, 'snd': 0}
        self.dataMessages = {'rcv': 0, 'snd': 0}

        # Padding after end of session
        self.totalPadding = 0

        # Initialize start time
        self.startTime = time.time()

        # Flag peer is padding or not
        self.is_peer_padding = False

        # Current iat
        self.current_iat = 0

        # bw differentials
        self.bw_diffs = []
