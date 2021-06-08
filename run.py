#!/usr/bin/env python3.5
# -*- coding: utf-8 -*-
""" Standard modules """
from argparse import ArgumentParser
import logging
import sys

""" Logger configuration """
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', 
    level=logging.WARNING)

log = logging.getLogger(__name__)

""" 3th party modules """
from telegram import *
from telegram.ext import * 

""" Local modules """
from src.core import TelegramAudioDownloadBot


# Verify: youtube-dl installation
try:
    import youtube_dl
except ImportError as e:
    log.fatal('Error: youtube-dl and/or youtube_dl python bindings are not installed.')
    sys.exit()

# Verify: config.py setup
try:
    import config
except ImportError as e:
    log.fatal('Error: No config.py file present. See config_template.py for further instructions.')
    sys.exit()


if __name__ == '__main__':
    parser = ArgumentParser(description='Run telegram bot')
    parser.add_argument('--verbose', action='store_true', dest='verbose', help='set loglevel to INFO')
    parser.add_argument('-d', '--debug', action='store_true', dest='debug', help='set loglevel to DEBUG')

    args = parser.parse_args()
    print(args)

    # logger initialization
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    elif args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    bot = TelegramAudioDownloadBot(token=config.BOT_TOKEN)
    bot.start()
