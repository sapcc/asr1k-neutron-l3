from oslo_config import cfg
from neutron.common import config as common_config
from asr1k_neutron_l3.common import config

from oslo_log import log as logging
LOG = logging.getLogger(__name__)

def main():
    import sys
    conf = cfg.CONF
    conf.register_opts(config.DEVICE_OPTS, "asr1k_devices")
    conf.register_opts(config.ASR1K_OPTS, "asr1k")
    conf.register_opts(config.ASR1K_L2_OPTS, "asr1k_l2")

    common_config.init(sys.argv[1:])
    common_config.setup_logging()

    from asr1k_neutron_l3.plugins.ml2.agents.asr1k_ml2_agent import ASR1KNeutronAgent

    agent = ASR1KNeutronAgent()

    # Start everything.
    LOG.info("Agent initialized successfully, now running... ")
    agent.daemon_loop()