import objc
from Foundation import NSAppleScript
import time
import pickle
import datetime
from urllib.parse import urlparse
import os
import os.path
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
import Quartz
import json
from threading import Thread
from glob import glob


class MACActions:
    @staticmethod
    def get_current_tab_safari():
        script = NSAppleScript.alloc().initWithSource_("tell application \"Safari\"\nif (count of windows) > 0 then\nset theWindow to front window\nif (count of tabs of theWindow) > 0 then\nset theTab to current tab of theWindow\nreturn URL of theTab\nend if\nend if\nend tell")

        errorDict = objc.nil
        result, error = script.executeAndReturnError_(errorDict)

        if result:
            tabURL = result.stringValue()
            return tabURL
        else:
            return "Error"

    @staticmethod
    def get_active_tab_chrome():
        script = NSAppleScript.alloc().initWithSource_('''
            tell application "Google Chrome"
                set theURL to URL of active tab of front window
                end tell
            return theURL
        ''')

        errorDict = objc.nil
        result, error = script.executeAndReturnError_(errorDict)
        if error is not None:
            print(error)
        if result:

            tabURL = result.stringValue()
            return tabURL
        else:
            return "Error"

    @staticmethod
    def get_active_app():

        # Get a list of all on-screen windows
        windowList = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)

        # Find the frontmost (i.e. currently focused) application
        frontmostApp = None
        for window in windowList:
            if window['kCGWindowLayer'] == 0:
                frontmostApp = window
                break

        # Extract the application name from the window information
        appName = frontmostApp['kCGWindowOwnerName']

        return appName

    @staticmethod
    def is_screen_locked():
        def is_screen_locked():
            session = Quartz.CGSessionCopyCurrentDictionary()
            return session.get('CGSSessionScreenIsLocked', 0)

        if is_screen_locked():
            True
        else:
            False

    @staticmethod
    def is_user_active(time_out):
        idle_time = Quartz.CGEventSourceSecondsSinceLastEventType(Quartz.kCGEventSourceStateHIDSystemState,
                                                                  Quartz.kCGAnyInputEventType)
        if idle_time < time_out:  # User is considered active if there was an input event within the last 5 seconds
            return True
        else:
            return False


def generate_report():
    files = glob('data/**.pickle')

    new_file_names = []

    for file in files:
        new_file_names.append(file.split('/')[-1].split('.')[0])

    files = sorted(new_file_names, key=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'))

    # get only last 30 days
    # files = files[-30:]

    all_tracked_apps = []
    for file in files:
        tracked_times = pickle.load(open(f'data/{file}.pickle', 'rb'))

        for app_name, window_name, time_used in tracked_times:
            if window_name is None:
                name = app_name
            else:
                name = f'{app_name}({window_name})'

            if name not in all_tracked_apps:
                all_tracked_apps.append(name)

    all_data = {}
    for app_name in all_tracked_apps:
        all_data[app_name] = []
        for i, file in enumerate(files):
            tracked_times = pickle.load(open(f'data/{file}.pickle', 'rb'))
            total_time_in_a_day = 0
            for current_app, window_name, time_used in tracked_times:
                if window_name is None:
                    name = current_app
                else:
                    name = f'{current_app}({window_name})'

                if name == app_name:
                    total_time_in_a_day += time_used

            all_data[app_name].append(round(round(total_time_in_a_day / 60, 1) / 60, 1))

    import plotly.graph_objects as go

    arr = []
    for key in all_data:
        arr.append(go.Bar(name=key, x=files, y=all_data[key], text=[str(i) + ' Hr' for i in all_data[key]]))

    fig = go.Figure(data=arr)

    fig.update_layout(barmode='stack')
    fig.write_html("report.html")


class AutomatedTaskTracker:
    def __init__(self):

        # get the current date and time
        now = datetime.datetime.now()
        # get the current day
        self.current_day = now.day
        self.today = datetime.date.today()

        self.current_app = None
        self.current_tab = None
        self.start_time = 0

        if os.path.exists(f'data/{datetime.date.today()}.pickle'):
            self.tracked_times = pickle.load(open(f'data/{self.today}.pickle', 'rb'))
        else:
            self.tracked_times = []

        with open('config.json', 'r') as file:
            self.config = json.loads(file.read())

        self.tracked_apps = self.config['global_property']['tracked_apps']

    def print_report(self):
        print("_________________________________________________")
        print('')
        all_data = dict()
        for app_name, window_name, time_used in self.tracked_times:
            if window_name is None:
                name = app_name
            else:
                name = f'{app_name}({window_name})'
            if name in all_data:
                all_data[name] += time_used
            else:
                all_data[name] = time_used

        for key in all_data:
            time_taken = round(all_data[key] / 60, 1)

            if time_taken > 60:
                time_taken = f'{round(time_taken / 60, 1)} hr'
            else:
                time_taken = f'{time_taken} min'

            print(f'{key} -> {time_taken}')

        print('')

    def save_tracking(self):

        if self.current_app is not None:
            now = datetime.datetime.now()
            self.tracked_times.append((self.current_app, self.current_tab, time.time() - self.start_time))
            pickle.dump(self.tracked_times, open(f'data/{self.today}.pickle', 'wb'))
            self.print_report()

            # A new day has started
            if now.day != self.current_day:
                self.tracked_times = []
                self.current_day = now.day
                self.today = datetime.date.today()
                thread = Thread(target=generate_report(), daemon=True)
                thread.start()

        self.current_app = None
        self.current_tab = None
        self.start_time = 0

    def is_working(self):
        app_name = MACActions.get_active_app()
        if app_name not in self.tracked_apps:
            return False, None, None
        else:
            if app_name in self.config:
                # Custom Config for the app
                if app_name == 'Safari':
                    url = MACActions.get_current_tab_safari()
                elif app_name == 'Google Chrome':
                    url = MACActions.get_active_tab_chrome()
                domain = urlparse(url).netloc

                tracked_domains = self.config[app_name]['tracked_domains']

                if domain in tracked_domains:
                    return True, app_name, domain
                else:
                    return False, None, None
            else:
                return True, app_name, None

    def main_loop(self):

        while True:
            if MACActions.is_screen_locked():
                if self.current_app is not None:
                    self.save_tracking()
            else:
                if MACActions.is_user_active(self.config["global_property"]["user_ideal_time"]):
                    flag_working, app_name, tab_name = self.is_working()
                    if not flag_working and self.current_app is not None:
                        # If user has switched to a different app, then save current work and reset all params
                        self.save_tracking()
                    elif flag_working:
                        # User just now started working
                        if self.current_app is None:
                            self.current_app = app_name
                            self.current_tab = tab_name
                            self.start_time = time.time()
                        elif self.current_app == app_name and self.current_tab == tab_name:
                            # User is still working on the same app and tab
                            continue
                        else:
                            # User is working on same App but switched tab
                            self.save_tracking()
                            self.current_app = app_name
                            self.current_tab = tab_name
                            self.start_time = time.time()
                    else:
                        # User is not working and current app is also None
                        pass

                else:
                    # User is ideal, save previous work
                    self.save_tracking()
            time.sleep(self.config["global_property"]["track_in_every_x_sec"])


if __name__ == '__main__':
    thread = Thread(target=generate_report(), daemon=True)
    thread.start()
    tt = AutomatedTaskTracker()
    tt.main_loop()
