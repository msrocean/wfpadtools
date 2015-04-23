"""Provide general tests for correctness of the wfpad protocol."""

# WFPadTools imports
import obfsproxy.common.log as logging
from obfsproxy.transports.wfpadtools import const
from obfsproxy.transports.wfpadtools.util import testutil as tu
from obfsproxy.test.transports.wfpadtools import wfpad_tester as wt

# Logging settings:
log = logging.get_obfslogger()


class TestReceivedBytes(wt.WFPadShimConfig, wt.SendDataServerTest, tu.STTest):
    opcode = const.OP_SEND_PADDING
    N, t = 5, 1
    args = [N, t]

    AFTER_SESSION_TIME = 5

    def test_correctness_of_transmission(self):
        """Test the correctness of the data manipulated by wfpad.

        During the setup of the test we sent `N` padding cells from server
        to client plus the string `TEST_MSG`.
        """
        # Test that server num snt msgs is equal to client num rcv msgs
        obs_cl_rcv_msgs = self.clientState["session"].numMessages['rcv']
        obs_sv_snd_msgs = self.serverState["session"].numMessages['snd']
        self.assertEqual(obs_cl_rcv_msgs, obs_sv_snd_msgs,
                         "Num msgs sent by server (%s) does not match num"
                         " msgs received by client (%s)."
                         % (obs_sv_snd_msgs, obs_cl_rcv_msgs))
        self.assertEqual(obs_cl_rcv_msgs, self.N + 1)

        # Test sent and received TOTAL bytes match
        obs_cl_rcv_total_bytes = self.clientState["session"].totalBytes['rcv']
        obs_sv_snd_total_bytes = self.serverState["session"].totalBytes['snd']
        self.assertEqual(obs_cl_rcv_total_bytes, obs_sv_snd_total_bytes,
                         "Total bytes sent by server (%s) does not match total"
                         " bytes received by client (%s)."
                         % (obs_sv_snd_total_bytes, obs_cl_rcv_total_bytes))
        self.assertEqual(obs_cl_rcv_msgs, (self.N + 1) * const.MPU)

        # Test sent and received DATA bytes match
        obs_cl_rcv_data_bytes = self.clientState["session"].dataBytes['rcv']
        obs_sv_snd_data_bytes = self.serverState["session"].dataBytes['snd']
        log.debug("Srv_snd_data_bytes = %s, Clt_rcv_data_bytes = %s",
                  obs_sv_snd_data_bytes, obs_cl_rcv_data_bytes)
        self.assertEqual(obs_cl_rcv_data_bytes, obs_sv_snd_data_bytes,
                         "Data bytes sent by server (%s) does not match data"
                         " bytes received by client (%s)."
                         % (obs_sv_snd_data_bytes, obs_cl_rcv_data_bytes))

        # Test number of rcv data bytes equals bytes of string that was sent
        databytes = len(wt.TEST_MSG)
        self.assertEqual(obs_cl_rcv_data_bytes, databytes,
                         "Data bytes received by client (%s) does not match "
                         " length of test string: %s."
                         % (obs_cl_rcv_data_bytes, wt.TEST_MSG))

        # Test total bytes is the amount of padding messages plus 1 (data message)
        # multiplied by the payload length plus the number of bytes of the string.
        # (recall that wfpad pads message length to MPU by default).
        totalbytes = (self.N + 1) * const.MPU
        self.assertEqual(obs_cl_rcv_total_bytes, totalbytes,
                         "Total bytes sent by server (%s) does not match total"
                         " bytes (%s)." % (obs_cl_rcv_total_bytes, totalbytes))
