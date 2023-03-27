import objc
from Foundation import NSAppleScript
import Quartz
import time
import pickle
import datetime
from urllib.parse import urlparse
import os


def get_current_tab_safari():
    import objc
    from Foundation import NSAppleScript

    script = NSAppleScript.alloc().initWithSource_(
        "tell application \"Safari\"\nif (count of windows) > 0 then\nset theWindow to front window\nif (count of tabs of theWindow) > 0 then\nset theTab to current tab of theWindow\nreturn URL of theTab\nend if\nend if\nend tell")

    errorDict = objc.nil
    result, error = script.executeAndReturnError_(errorDict)

    if result:
        tabURL = result.stringValue()
        return tabURL
    else:
        return "Error"


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


def get_active_app():
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

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


import os.path


def print_report(tracked_times):

    print("_________________________________________________")
    print('')
    all_data = dict()
    for app_name, window_name, time_used in tracked_times:
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


def save_tracking(tracked_times, app_name, window_name, start_time):
    if app_name is not None:
        tracked_times.append((app_name, window_name, time.time() - start_time))
        pickle.dump(tracked_times, open(f'{datetime.date.today()}.pickle', 'wb'))
        print_report(tracked_times)
    return None, None, 0


tracked_apps = ['PyCharm', 'Safari', 'Google Chrome']
chrome_tracked_sites = ['www.educative.io', 'www.algoexpert.io','leetcode.com']


def is_working():
    app_name = get_active_app()
    if app_name not in tracked_apps:
        return False, None, None
    else:
        if app_name == 'Safari':
            URL = get_current_tab_safari()
            domain = urlparse(URL).netloc
            if 'youtube.com' in domain:
                return True, app_name, domain
            else:
                return False, None, None
        elif app_name == 'Google Chrome':
            URL = get_active_tab_chrome()
            domain = urlparse(URL).netloc
            if domain in chrome_tracked_sites:
                return True, app_name, domain
            else:
                return False, None, None

        elif app_name in tracked_apps:
            return True, app_name, None


def main_loop():
    import Quartz
    import time

    current_app = None
    current_tab = None
    start_time = 0

    if os.path.exists(f'{datetime.date.today()}.pickle'):
        tracked_times = pickle.load(open(f'{datetime.date.today()}.pickle', 'rb'))
    else:
        tracked_times = []

    def is_user_active():
        idle_time = Quartz.CGEventSourceSecondsSinceLastEventType(Quartz.kCGEventSourceStateHIDSystemState,
                                                                  Quartz.kCGAnyInputEventType)
        if idle_time < 120:  # User is considered active if there was an input event within the last 5 seconds
            return True
        else:
            return False

    while True:
        if is_screen_locked():
            if current_app is not None:
                current_app, current_tab, start_time = save_tracking(tracked_times, current_app, current_tab,
                                                                     start_time)
        else:
            if is_user_active():
                flag_working, app_name, tab_name = is_working()
                if not flag_working and current_app is not None:
                    current_app, current_tab, start_time = save_tracking(tracked_times, current_app, current_tab,
                                                                         start_time)
                else:
                    if current_app is None:
                        current_app = app_name
                        current_tab = tab_name
                        start_time = time.time()
                    elif current_app == app_name and current_tab == tab_name:
                        continue
                    else:
                        save_tracking(tracked_times, current_app, current_tab, start_time)
                        current_app = app_name
                        current_tab = tab_name
                        start_time = time.time()

            else:
                # User is ideal
                current_app, current_tab, start_time = save_tracking(tracked_times, current_app, current_tab,
                                                                     start_time)

        time.sleep(1)


def is_screen_locked():
    import Quartz

    def is_screen_locked():
        session = Quartz.CGSessionCopyCurrentDictionary()
        return session.get('CGSSessionScreenIsLocked', 0)

    if is_screen_locked():
        True
    else:
        False


main_loop()
