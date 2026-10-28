# ==============================================================================
# _inline.py - Keyboard Buttons
# ==============================================================================
# Helper methods to generate all the inline keyboards (play controls, help menus, etc).
# ==============================================================================

from pyrogram import types

from HasiiMusic import app, config, db, lang, settings



class Inline:
    def __init__(self):
        self.ikm = types.InlineKeyboardMarkup
        self.ikb = types.InlineKeyboardButton

    def cancel_dl(self, text) -> types.InlineKeyboardMarkup:
        return self.ikm([[self.ikb(text=text, callback_data=f"cancel_dl")]])

    def controls(
        self,
        chat_id: int,
        status: str = None,
        timer: str = None,
        remove: bool = False,
        is_playing: bool = True,
    ) -> types.InlineKeyboardMarkup:
        keyboard = []
        if status:
            keyboard.append(
                [self.ikb(
                    text=status, callback_data=f"controls status {chat_id}")]
            )
        elif timer:
            keyboard.append(
                [self.ikb(
                    text=timer, callback_data=f"controls status {chat_id}")]
            )

        if not remove:
            # Seek buttons row
            keyboard.append(
                [
                    self.ikb(
                        text="« 30", callback_data=f"controls seek_back_30 {chat_id}"),
                    self.ikb(
                        text="« 10", callback_data=f"controls seek_back_10 {chat_id}"),
                    self.ikb(
                        text="10 »", callback_data=f"controls seek_forward_10 {chat_id}"),
                    self.ikb(
                        text="30 »", callback_data=f"controls seek_forward_30 {chat_id}"),
                ]
            )
            # Main control buttons row
            keyboard.append(
                [
                    self.ikb(
                        text="❚❚" if is_playing else "▷",
                        callback_data=f"controls {'pause' if is_playing else 'resume'} {chat_id}"
                    ),
                    self.ikb(
                        text="◁◁", callback_data=f"controls previous {chat_id}"),
                    self.ikb(
                        text="↻", callback_data=f"controls replay {chat_id}"),
                    self.ikb(
                        text="▷▷", callback_data=f"controls skip {chat_id}"),
                    self.ikb(
                        text="■", callback_data=f"controls stop {chat_id}"),
                ]
            )
            # Autoplay toggle and close
            keyboard.append(
                [
                    self.ikb(
                        text=self.autoplay_label(db.autoplay_cached(chat_id)),
                        callback_data=f"controls autoplay {chat_id}"),
                    self.ikb(
                        text="✕ ᴄʟᴏꜱᴇ", callback_data=f"controls close {chat_id}"),
                ]
            )
        return self.ikm(keyboard)

    @staticmethod
    def autoplay_label(on: bool) -> str:
        return "◉ ᴀᴜᴛᴏᴘʟᴀʏ" if on else "○ ᴀᴜᴛᴏᴘʟᴀʏ"

    def help_markup(
        self, _lang: dict, back: bool = False
    ) -> types.InlineKeyboardMarkup:
        if back:
            rows = [
                [
                    self.ikb(text="« ʙᴀᴄᴋ", callback_data="help_main"),
                ]
            ]
        else:
            rows = [
                [
                    self.ikb(text="◈ ᴘʟᴀʏ", callback_data="help_play"),
                    self.ikb(text="◈ ǫᴜᴇᴜᴇ", callback_data="help_queue"),
                    self.ikb(text="◈ ᴀᴜᴛᴏᴘʟᴀʏ", callback_data="help_autoplay"),
                ],
                [
                    self.ikb(text="◈ ʟᴏᴏᴘ", callback_data="help_loop"),
                    self.ikb(text="◈ ꜱᴇᴇᴋ", callback_data="help_seek"),
                    self.ikb(text="◈ ᴀᴅᴍɪɴꜱ", callback_data="help_admins"),
                ],
                [
                    self.ikb(text="◇ ᴀᴜᴛʜ", callback_data="help_auth"),
                    self.ikb(text="◇ ʙʟ-ᴄʜᴀᴛ", callback_data="help_blchat"),
                    self.ikb(text="◇ ʙʟ-ᴜꜱᴇʀ", callback_data="help_bluser"),
                ],
                [
                    self.ikb(text="◇ ᴘɪɴɢ", callback_data="help_ping"),
                    self.ikb(text="◇ ꜱᴛᴀᴛꜱ", callback_data="help_stats"),
                    self.ikb(text="◇ ꜱᴜᴅᴏ", callback_data="help_sudo"),
                ],
                [
                    self.ikb(text="◇ ʙʀᴏᴀᴅᴄᴀꜱᴛ", callback_data="help_broadcast"),
                    self.ikb(text="« ʙᴀᴄᴋ", callback_data="start"),
                ],
            ]
        return self.ikm(rows)


    def link_buttons(self) -> list:
        """Support and channel buttons. Only the ones the owner has set."""
        row = []
        if settings.get("support_chat"):
            row.append(self.ikb(text="◇ ꜱᴜᴘᴘᴏʀᴛ", url=config.SUPPORT_CHAT))
        if settings.get("support_channel"):
            row.append(self.ikb(text="◇ ᴜᴘᴅᴀᴛᴇꜱ", url=config.SUPPORT_CHANNEL))
        return row

    def ping_markup(self, text: str) -> types.InlineKeyboardMarkup:
        rows = []
        links = self.link_buttons()
        if links:
            rows.append(links)
        rows.append(
            [self.ikb(text="＋ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ", url=f"https://t.me/{app.username}?startgroup=true")]
        )
        return self.ikm(rows)

    def play_queued(
        self, chat_id: int, item_id: str, _text: str
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.ikb(
                        text="▷", callback_data=f"controls resume {chat_id}"),
                    self.ikb(
                        text="❚❚", callback_data=f"controls pause {chat_id}"),
                    self.ikb(
                        text="▷▷", callback_data=f"controls skip {chat_id}"),
                    self.ikb(
                        text="■", callback_data=f"controls stop {chat_id}"),
                ],
                [
                    self.ikb(
                        text="✕ ᴄʟᴏꜱᴇ", callback_data=f"controls close {chat_id}"),
                ]
            ]
        )

    def queue_markup(
        self, chat_id: int, _text: str, playing: bool
    ) -> types.InlineKeyboardMarkup:
        _action = "pause" if playing else "resume"
        return self.ikm(
            [[self.ikb(
                text=_text, callback_data=f"controls {_action} {chat_id} q")]]
        )

    def settings_markup(
        self, lang: dict, admin_only: bool, language: str, chat_id: int
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.ikb(
                        text=lang["play_mode"] + " ›",
                        callback_data=f"controls status {chat_id}",
                    ),
                    self.ikb(text=admin_only, callback_data="playmode"),
                ],
            ]
        )

    def start_key(
        self, lang: dict, private: bool = False
    ) -> types.InlineKeyboardMarkup:
        rows = [
            [
                self.ikb(
                    text="＋ " + lang["add_me"],
                    url=f"https://t.me/{app.username}?startgroup=true",
                )
            ],
            [self.ikb(text="◈ " + lang["help"], callback_data="help")],
        ]
        links = self.link_buttons()
        if links:
            rows.append(links)
        # Owner button and any custom buttons come from the owner panel
        rows.append(
            [self.ikb(text="\u266a " + settings.get("owner_name"), url=settings.owner_link)]
        )
        for label, url in settings.get("extra_buttons"):
            rows.append([self.ikb(text=label, url=url)])
        if private and settings.get("source_url"):
            rows.append([self.ikb(text=lang["source"], url=settings.get("source_url"))])
        return self.ikm(rows)

    def yt_key(self, link: str) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.ikb(text="ᴄᴏᴘʏ ʟɪɴᴋ", copy_text=link),
                    self.ikb(text="ᴏᴘᴇɴ ɪɴ ʏᴏᴜᴛᴜʙᴇ", url=link),
                ],
            ]
        )
