import logging
import os, subprocess
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GLib
from ks_includes.screen_panel import ScreenPanel


# Same as ALLOWED_SERVICES in moonraker
# https://github.com/Arksine/moonraker/blob/master/moonraker/components/machine.py
ALLOWED_SERVICES = (
    "crowsnest",
    "MoonCord",
    "moonraker",
    "moonraker-telegram-bot",
    "klipper",
    "KlipperScreen",
    "sonar",
    "webcamd",
)


class ListItem(Gtk.Box):
    def __init__(self, title):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.get_style_context().add_class("frame-item")
        self.set_hexpand(True)
        self.set_vexpand(False)
        self.set_valign(Gtk.Align.CENTER)
        self.title_label = Gtk.Label(label=title)
        self.title_label.set_vexpand(False)
        self.title_label.set_hexpand(False)
        self.pack_start(self.title_label, False, False, 6)

    def add_side_widget(self, button):
        button.set_vexpand(False)
        button.set_hexpand(False)
        self.pack_end(button, False, False, 6)

class Panel(ScreenPanel): # todo, add error handling, soft and hard recovery options. add version, add machine serial, add zerotier ID,
    def __init__(self, screen, title):
        super().__init__(screen, title)
        self.refresh = None
        self.update_dialog = None

        main_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        menu_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6) 
        self.lists_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        ### --- MENU BAR --- ###
        self.refresh = self._gtk.Button('refresh', _('Check for Updates'), 'color2')
        self.refresh.connect("clicked", self.refresh_updates)
        self.refresh.set_vexpand(False)

        reboot = self._gtk.Button('refresh', _('Restart'), 'color3')
        reboot.connect("clicked", self.reboot_poweroff, "reboot")
        reboot.set_vexpand(False)
        shutdown = self._gtk.Button('shutdown', _('Shutdown'), 'color4')
        shutdown.connect("clicked", self.reboot_poweroff, "poweroff")
        shutdown.set_vexpand(False)

        menu_bar.add(self.refresh)
        menu_bar.add(reboot)
        menu_bar.add(shutdown)

        ### -- Software Updates / ETC --- ###
        self.update_all_button = self._gtk.Button('arrow-up', _('Update Available'), 'color1', scale=0.7)
        self.update_all_button.connect("clicked", self.show_update_info) # Might have issues with modified repos, switch to ZIP updates instead?

        updates_item = ListItem("Software Updates")
        updates_item.add_side_widget(self.update_all_button)

        node_id = ListItem("Support Node ID")
        node_id_label = Gtk.Label(label=self.get_zerotier_node())
        node_id.add_side_widget(node_id_label)

        self.lists_box.pack_start(updates_item, False, False, 0)
        self.lists_box.pack_start(node_id, False, False, 0)

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        scroll.add(self.lists_box)




        main_frame.pack_start(scroll, True, True, 6)
        main_frame.pack_end(menu_bar, False, False, 6)

        self.get_updates()

        if(not self.should_update()):
            self.update_all_button.set_sensitive(False)
            self.update_all_button.set_label("Up To Date")

        self.content.add(main_frame)

    def activate(self):
        self.get_updates()
        if(self.should_update()):
            self.update_all_button.set_sensitive(True)
            self.update_all_button.set_label("Update Available")
        else:
            self.update_all_button.set_sensitive(False)
            self.update_all_button.set_label("Up To Date")

    def refresh_updates(self, widget=None):
        self.refresh.set_sensitive(False)
        self._screen.show_popup_message(_("Checking for updates, please wait..."), level=1)
        GLib.timeout_add_seconds(1, self.get_updates, "true")

    def get_updates(self, refresh="false"):
        update_resp = self._screen.apiclient.send_request(f"machine/update/status?refresh={refresh}")
        if not update_resp:
            self.update_status = {}
            logging.info("No update manager configured")
        else:
            self.update_status = update_resp['result']

        self.refresh.set_sensitive(True)
        self._screen.close_popup_message()

    def restart_service(self, widget, program):
        if program not in ALLOWED_SERVICES:
            return

        logging.info(f"Restarting service: {program}")
        self._screen._ws.send_method("machine.services.restart", {"service": program})

    def show_update_info(self, widget):
        is_dirty = False

        for program in self.update_status['version_info']:
            is_dirty = self.program_is_dirty(program)

            if is_dirty:
                break

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)

        label = Gtk.Label()
        label.set_line_wrap(True)

        if(is_dirty):
            label.set_markup('<b>' + _("Incompatible changes detected, reeset? </b>\n (User changes detected and will be reset, you may update again afterwards)"))
        else: 
            label.set_markup('<b>' + _("Perform a full update?") + '</b>')

        vbox.add(label)

        scroll.add(vbox)

        buttons = [
            {"name": _("Update"), "response": Gtk.ResponseType.OK},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.update_confirm, program)
        dialog.set_title(_("Update"))

    def update_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Updating system")
            self.update_system(self)

    def program_is_dirty(self, program):
        """ Checks if the repository for a program is dirty """
        program = self.update_status['version_info'][program]
        if 'configured_type' in program:
                if program['configured_type'] == 'git_repo':
                    if not program['is_valid'] or program['is_dirty']:
                        return True
        return False
    
    def update_system(self, widget):
        """ Performs a full system update, resetting any dirty repos """

        if self._screen.updating or not self.update_status:
            return
        
        for program in self.update_status['version_info']:
            if (self.program_is_dirty(program)):
                logging.debug(f"Repo {program} is dirty, hard resetting repo...")
                self.reset_repo(self, program, True)

        logging.debug("Sending full update request to moonraker")
        self._screen._ws.send_method("machine.update.full")

    def reset_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Recovering hard {program}")
            self.reset_repo(self, program, True)
        if response_id == Gtk.ResponseType.APPLY:
            logging.debug(f"Recovering soft {program}")
            self.reset_repo(self, program, False)

    def reset_repo(self, widget, program, hard):
        if self._screen.updating:
            return
        self._screen.base_panel.show_update_dialog()
        msg = _("Starting recovery for") + f' {program}...'
        self._screen._websocket_callback("notify_update_response",
                                         {'application': {program}, 'message': msg, 'complete': False})
        logging.info(f"Sending machine.update.recover name: {program} hard: {hard}")
        self._screen._ws.send_method("machine.update.recover", {"name": program, "hard": hard})

    def update_program(self, widget, program):
        if self._screen.updating or not self.update_status:
            return

        if program in self.update_status['version_info']:
            info = self.update_status['version_info'][program]
            logging.info(f"program: {info}")
            if "package_count" in info and info['package_count'] == 0 \
                    or "version" in info and info['version'] == info['remote_version']:
                return
        self._screen.base_panel.show_update_dialog()
        msg = _("Updating") if program == "full" else _("Starting update for") + f' {program}...'
        self._screen._websocket_callback("notify_update_response",
                                         {'application': {program}, 'message': msg, 'complete': False})

        if program in ['klipper', 'moonraker', 'system', 'full']:
            logging.info(f"Sending machine.update.{program}")
            self._screen.dd.send_method(f"machine.update.{program}")
        else:
            logging.info(f"Sending machine.update.client name: {program}")
            self._screen._ws.send_method("machine.update.client", {"name": program})

    def should_update(self) -> bool:
        """ Checks all packages to determine if ther system should update """
        version_information = self.update_status['version_info']
        programs = sorted(list(version_information))

        for program in programs:
            if program == "system":
                continue
            else:
                if(self.is_update_available(program)):
                    return True
        
        return False # No non-system updates were available. Only update system if a package update also exists.

    def is_update_available(self, p):
        """ Checks specific package for an update """

        info = self.update_status['version_info'][p]
        if p == "system":
            if info['package_count'] == 0:
                return False
            else:
                return True
        elif info['version'] == info['remote_version']:
            return False
        else:
            return True

    def update_program_info(self, p):

        if 'version_info' not in self.update_status or p not in self.update_status['version_info']:
            logging.info(f"Unknown version: {p}")
            return

        if(not self.is_update_available(p)):
            self.labels[f"{p}_status"].set_label(f" {p} no update {self.should_update()} ")
        else:
            self.labels[f"{p}_status"].set_label(f"{p} some update")

        return

        info = self.update_status['version_info'][p]

        if p == "system":
            self.labels[p].set_markup("<b>System</b>")
            if info['package_count'] == 0:
                self.labels[f"{p}_status"].set_label(_("Up To Date"))
                self.labels[f"{p}_status"].get_style_context().remove_class('update')
                self.labels[f"{p}_status"].set_sensitive(False)
            else:
                self._needs_update(p, local="", remote=info['package_count'])

        elif 'configured_type' in info and info['configured_type'] == 'git_repo':
            if info['is_valid'] and not info['is_dirty']:
                if info['version'] == info['remote_version']:
                    self._already_updated(p, info)
                    self.labels[f"{p}_status"].get_style_context().remove_class('invalid')
                else:
                    self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}")
                    self._needs_update(p, info['version'], info['remote_version'])
            else:
                logging.info(f"Invalid {p} {info['version']}")
                self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
                self.labels[f"{p}_status"].set_label(_("Invalid"))
                self.labels[f"{p}_status"].get_style_context().add_class('invalid')
                self.labels[f"{p}_status"].set_sensitive(True)
        elif 'version' in info and info['version'] == info['remote_version']:
            self._already_updated(p, info)
        else:
            self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}")
            self._needs_update(p, info['version'], info['remote_version'])

    def _already_updated(self, p, info):
        logging.info(f"{p} {info['version']}")
        self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
        self.labels[f"{p}_status"].set_label(_("Up To Date"))
        self.labels[f"{p}_status"].get_style_context().remove_class('update')
        self.labels[f"{p}_status"].set_sensitive(False)

    def _needs_update(self, p, local="", remote=""):
        logging.info(f"{p} {local} -> {remote}")
        self.labels[f"{p}_status"].set_label(_("Update"))
        self.labels[f"{p}_status"].get_style_context().add_class('update')
        self.labels[f"{p}_status"].set_sensitive(True)

    def reboot_poweroff(self, widget, method):
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        if method == "reboot":
            label = Gtk.Label(label=_("Are you sure you wish to reboot the system?"))
        else:
            label = Gtk.Label(label=_("Are you sure you wish to shutdown the system?"))
        vbox.add(label)
        scroll.add(vbox)
        buttons = [
            {"name": _("Host"), "response": Gtk.ResponseType.OK},
            {"name": _("Printer"), "response": Gtk.ResponseType.APPLY},
            {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL}
        ]
        dialog = self._gtk.Dialog(self._screen, buttons, scroll, self.reboot_poweroff_confirm, method)
        if method == "reboot":
            dialog.set_title(_("Restart"))
        else:
            dialog.set_title(_("Shutdown"))

    def reboot_poweroff_confirm(self, dialog, response_id, method):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            if method == "reboot":
                os.system("systemctl reboot")
            else:
                os.system("systemctl poweroff")
        elif response_id == Gtk.ResponseType.APPLY:
            if method == "reboot":
                self._screen._ws.send_method("machine.reboot")
            else:
                self._screen._ws.send_method("machine.shutdown")

    def get_zerotier_node(self):
        node_id = subprocess.check_output(['sudo', 'zerotier-cli', 'status']).decode()
        node_id = node_id.split(" ")[2]

        if len(node_id) < 10:
            return "N/A"
        else:
            return node_id