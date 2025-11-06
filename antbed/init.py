#!/usr/bin/env python3
import logging
from typing import Literal

from antgent.init import init as antgent_init

from antbed.config import ConfigSchema

logger = logging.getLogger(__name__)


def init(config: ConfigSchema, mode: Literal["server", "worker"] = "server", extra=None):
    logger.info("antbed with mode: %s", mode)
    logger.debug("init config: %s", config)
    env = config.app.env
    antgent_init(config, env=env, mode=mode, extra=extra)
