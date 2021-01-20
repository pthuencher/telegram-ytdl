#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Standard modules """
import logging

""" 3th party modules """
from telegram import *
from telegram.ext import * 

log = logging.getLogger(__name__)



def handler(bot, update, error):
    log.error('Update "%s" caused error "%s"', update, error)
    update.message.reply_text(
        text='<strong>error :(</strong>',
        parse_mode=ParseMode.HTML)

