#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Standard modules """
import subprocess
import logging
import datetime
import os
import importlib
from functools import partial

""" 3th party modules """
from telegram import *
from telegram.ext import * 
import youtube_dl
from pydub import AudioSegment

""" Local modules """
import src.utils
import src.history
import src.whitelist
import config
import os

log = logging.getLogger(__name__)


# Constants
YT_URL_PLAYLIST_ATTR = "&list="


def authorize(update, admin_only=False):
    userid = str(update.effective_user.id)
    whitelist = src.whitelist.get()

    if admin_only:
        if userid == config.SERVICE_ACCOUNT_CHAT_ID:
            return True
        else:
            return False
    elif whitelist and userid in whitelist:
        return True
    else:
        log.warning("Unauthorized access from: " + str(update.effective_user))
        # send msg to unauthorized users
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Request Access", callback_data=str(update.effective_user.name) + " (" + userid + ")")]])
        update.message.reply_text(
            text="<b>Error: not authorized.</b>", 
            parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    
    return False

def UnauthorizedHandler():

    def handler(bot, update):
        """ This function handels the "Request Access" button.  """
        query = update.callback_query
        
        bot.send_message(chat_id=config.SERVICE_ACCOUNT_CHAT_ID, text='<b>Access request by </b><i>%s</i>' % query.data, parse_mode=ParseMode.HTML)
        bot.send_message(chat_id=query.message.chat_id, text="<b>Request send.</b>", parse_mode=ParseMode.HTML)

    return CallbackQueryHandler(handler)

def StartCommandHandler():

    def handler(bot, update):
        if not authorize(update):
            return
        
        update.message.reply_text(
            text='<strong>ytdl-telegram-bot</strong>\n<i>v2020.11.18</i>\nhttps://github.com/pthuencher/python-telegram-bot-audio-downloader\n\n<strong>Share a link or enter a URL to download audio file.</strong>\n\nyoutube.com \u2714\nsoundcloud.com \u2714\n\nUse /update to fetch most recent youtube-dl /version.', 
            parse_mode=ParseMode.HTML)

    return CommandHandler('start', handler)

def VersionCommandHandler():

    def handler(bot, update):
        if not authorize(update):
            return
        
        try:
            resp = subprocess.check_output(['youtube-dl', '--version'])
            version = resp.decode('utf-8')
            update.message.reply_text(
                text='<strong>youtube-dl:</strong> %s' % version,
                parse_mode=ParseMode.HTML)
        except subprocess.CalledProcessError as e:
            update.message.reply_text(
                text='<i>Failed to determine version of youtube-dl</i>\n%r' % e,
                parse_mode=ParseMode.HTML)	

    return CommandHandler('version', handler)

def UpdateCommandHandler():

    def handler(bot, update):
        if not authorize(update):
            return
        
        try:
            resp = subprocess.check_output(['pip3.5', 'install', 'youtube-dl', '--upgrade'])
            resp = resp.decode('utf-8')
            update.message.reply_text(
                text=resp,
                parse_mode=ParseMode.HTML)
        except subprocess.CalledProcessError as e:
            update.message.reply_text(
                text='<i>Failed to update youtube-dl</i>\n%r' % e,
                parse_mode=ParseMode.HTML)

    return CommandHandler('update', handler)


def HistoryCommandHandler():

    def handler(bot, update):
        if not authorize(update):
            return
        
        history = src.history.get_history()

        if history is None:
            update.message.reply_text(
                text='<i>No history available</i>',
                parse_mode=ParseMode.HTML)
        else:
            update.message.reply_text(
                text='<i>last %d downloads</i>\n%s' % (history.count('\n'), history),
                parse_mode=ParseMode.HTML)


    return CommandHandler('history', handler)


def WhitelistCommandHandler():

    def handler(bot, update):
        if not authorize(update, admin_only=True):
            return
        
        uid = update.message.text[11:]
        if not uid.strip():
           update.message.reply_text(text=str(src.whitelist.get()))
        else:
            src.whitelist.add(update.message.text[11:]) # trim /whitelist from message
            update.message.reply_text(text='<i>done.</i>', parse_mode=ParseMode.HTML)


    return CommandHandler('whitelist', handler)


def MainConversationHandler():

    # Conversation stages
    CHOOSE_FORMAT, CHOOSE_LENGTH, CHECKOUT = range(3)


    def handle_abort(bot, update, last_message_id=None):

        chat_id = update.message.chat_id
        msg_id = update.message.message_id

        bot.send_message(chat_id=chat_id, text='<i>aborted</i>', parse_mode=ParseMode.HTML)
        bot.delete_message(chat_id=chat_id, message_id=msg_id)

        if last_message_id:
            bot.delete_message(chat_id=chat_id, message_id=last_message_id)

        return ConversationHandler.END

    def handle_error(bot, update, last_message_id=None, error_message=None, url=None):

        chat_id = update.message.chat_id
        msg_id = update.message.message_id

        log.info('A user got "%s" error by using "%s" as input' % (error_message, url))

        if error_message is None:
            error_message = 'An unspecified error occured! :('

        bot.send_message(chat_id=chat_id, text='<strong>error:</strong> <i>%s</i>' % error_message, parse_mode=ParseMode.HTML) #, reply_markup=reply_markup)
        #bot.delete_message(chat_id=chat_id, message_id=msg_id)

        if last_message_id:
            bot.delete_message(chat_id=chat_id, message_id=last_message_id)

        return ConversationHandler.END

    def handle_cancel(update, context):
        return handle_abort(context.bot, update)


    def handle_incoming_url(bot, update, chat_data):
        if not authorize(update):
            return
        
        """ Handle incoming url """
        url = src.utils.parse_url(update.message.text)
        log.info('Incoming url "%s"' % url)

        # remove playlist information from url
        if YT_URL_PLAYLIST_ATTR in url:
            url = url[:url.index(YT_URL_PLAYLIST_ATTR)]

        bot.send_chat_action(update.message.chat_id, action=ChatAction.TYPING)

        try:
            info_dict = src.utils.get_info(url)
            chat_data['metadata'] = {
                'url': url,
                'title': info_dict['title'] if 'title' in info_dict else '',
                'performer': info_dict['creater'] if 'creater' in info_dict else info_dict['uploader'],
                'duration': str(datetime.timedelta(seconds=int(info_dict['duration']))) if 'duration' in info_dict else 'unknown',
                'thumb': info_dict['thumbnail'] if 'thumbnail' in info_dict else '',
            }
        except (youtube_dl.utils.DownloadError, youtube_dl.utils.ExtractorError) as e:
            return handle_error(bot, update, error_message='something went wrong. try to /update to newest youtube-dl version.', url=url)


        # create format keyboard
        keyboard = [['video', 'audio'], ['abort']]

        bot.send_message(
            chat_id=update.message.chat_id, 
            text='<strong>%(title)-70s</strong>\n<i>by %(performer)s</i>' % chat_data['metadata'],
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))

        reply = update.message.reply_text(
            text='<i>** choose format **</i>', 
            parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))

        chat_data['url'] = url
        chat_data['info_dict'] = info_dict
        chat_data['last_message_id'] = reply.message_id

        return CHOOSE_FORMAT



    def handle_format_selection(bot, update, chat_data):

        ext = update.message.text
        msg = update.message
        chat_id = msg.chat_id


        if ext == 'abort': return handle_abort(bot, update, chat_data['last_message_id'])

        bot.send_chat_action(update.message.chat_id, action=ChatAction.TYPING)
        # remove previous messages
        bot.delete_message(chat_id=chat_id, message_id=chat_data['last_message_id'])
        bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
        # send new message
        bot.send_message(chat_id=chat_id, 
            text='<strong>Format:</strong> <i>%s</i>' % ext, 
            parse_mode=ParseMode.HTML)

        # create format keyboard
        keyboard = [['abort', 'full']]

        reply = update.message.reply_text(
            '<i>** select start / end ** { HH:MM:SS-HH:MM:SS }</i>', 
            parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))

        chat_data['ext'] = ext
        chat_data['last_message_id'] = reply.message_id

        return CHOOSE_LENGTH



    def handle_length_selection(bot, update, chat_data):
        
        length = update.message.text
        msg = update.message
        chat_id = msg.chat_id

        if length == 'abort': return handle_abort(bot, update, chat_data['last_message_id'])

        if length != 'full':
            if not src.utils.length_ok(length):
                return handle_error(bot, update, error_message='could not extract length from given input', url=chat_data['url'])

        bot.send_chat_action(update.message.chat_id, action=ChatAction.TYPING)
        # remove previous messages
        bot.delete_message(chat_id=chat_id, message_id=chat_data['last_message_id'])
        bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
        # send new message
        bot.send_message(chat_id=chat_id, 
            text='<strong>Length:</strong> <i>%s</i>' % length, 
            parse_mode=ParseMode.HTML)

        # create checkout keyboard
        keyboard = [['abort', 'download']]

        reply = update.message.reply_text(
            '<i>** please confirm **</i>', 
            parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))

        chat_data['length'] = length
        chat_data['last_message_id'] = reply.message_id

        if chat_data['ext'] == 'video' and chat_data['length'] != 'full':
            return handle_error(bot, update, error_message='currently it is not possible to cut video files')

        return CHECKOUT



    def handle_checkout(bot, update, chat_data):
        if not authorize(update):
            return
        

        confirmed = update.message.text
        msg = update.message
        chat_id = msg.chat_id

        if confirmed == 'abort': return handle_abort(bot, update, chat_data['last_message_id'])

        # remove previous messages
        bot.delete_message(chat_id=chat_id, message_id=chat_data['last_message_id'])
        bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
        # send new message
        status_msg = bot.send_message(chat_id=chat_id, text='<i>.. processing (1/2) ..</i>', parse_mode=ParseMode.HTML)
        bot.send_chat_action(update.message.chat_id, action=ChatAction.RECORD_AUDIO)

        # download audio
        try:
            filename = src.utils.get_download(chat_data['url'], chat_data['ext'], chat_data['length'])
        except youtube_dl.utils.DownloadError as e:
            return handle_error(bot, update, error_message='failed to download audio as .%s' % chat_data['ext'], url=chat_data['url'])


        # (OPTIONAL) cut audio
        if chat_data['length'] != 'full':
            length = chat_data['length'].split('-')
            start = [int(x) for x in length[0].split(':')]
            end = [int(x) for x in length[1].split(':')]


            log.debug('Try to cut file "%s" to %s' % (filename, chat_data['length']))
            try:
                song = AudioSegment.from_file(filename)
                extract = song[src.utils.length_to_msec(length[0]):src.utils.length_to_msec(length[1])]
                extract.export(filename, format="mp3")
            except:
                return handle_error(bot, update, error_message='Failed to cut audio', url=chat_data['url'])


        # update status message
        bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        status_msg = bot.send_message(chat_id=chat_id, text='<i>.. sending audio (2/2) ..</i>', parse_mode=ParseMode.HTML)
        bot.send_chat_action(update.message.chat_id, action=ChatAction.UPLOAD_AUDIO)


        if not src.utils.size_ok(filename):
            """ File NOT OK """
            # remove please wait message
            bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
            # remove tmp file from disk
            src.utils.remove_file(filename)
            return handle_error(bot, update, error_message='The audio file is too large (max. 50MB)', url=chat_data['url'])
        else:
            """ File OK """
            # open audio file for transfer    
            try:
                with open(filename, 'rb') as fd:
                    log.info('Start transferring file %s to client' % filename)
                    if 'video' in chat_data['ext']:
                        bot.send_video(chat_id=chat_id, video=fd, timeout=180, **chat_data['metadata'])
                    else:
                        bot.send_audio(chat_id=chat_id, audio=fd, timeout=180, **chat_data['metadata'])
                    log.info('Finished transferring file %s' % filename)
            except FileNotFoundError as e:
                    return handle_error(bot, update, error_message='failed to send file (%s) from %s' % chat_data['ext'], url=chat_data['url'])

        # add download to history
        src.history.add_history(chat_data['url'])
        # remove please wait message
        bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        # remove tmp file from disk
        src.utils.remove_file(filename)

        return ConversationHandler.END



    return ConversationHandler(
        entry_points=[MessageHandler(Filters.all, handle_incoming_url, pass_chat_data=True)],

        states={
            CHOOSE_FORMAT: [MessageHandler(Filters.all, handle_format_selection, pass_chat_data=True)],
            CHOOSE_LENGTH: [MessageHandler(Filters.all, handle_length_selection, pass_chat_data=True)],

            CHECKOUT: [MessageHandler(Filters.all, handle_checkout, pass_chat_data=True)]
        },

        fallbacks=[CommandHandler('cancel', handle_cancel)],
        run_async_timeout=999
    )
