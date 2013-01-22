import datetime
import logging
import os
import pytz

import pickle  # For development

import fbs_settings
import fitbit

logging.basicConfig(level=logging.DEBUG)


class FitBitSplunk():

    def __init__(self):
        pass

    def get_profile(self):
        user = self.fb.user_profile_get()
        self.user_profile = user['user']

    def login(self, consumer_key, consumer_secret, user_key, user_secret,
              get_profile=True):
        fb = fitbit.Fitbit(consumer_key, consumer_secret,
                           user_key=user_key, user_secret=user_secret)
        self.fb = fb
        if get_profile:
            self.get_profile()

    def get_one_day(self, day):
        url = ('%s/%s/user/%s/activities/steps/date/%s/1d.json' %
               (self.fb.API_ENDPOINT, self.fb.API_VERSION, '-', day))
        one_day = self.fb.make_request(url=url)
        return one_day

    def save_one_day_to_file(self, one_day, output_path):
        output = open(output_path, 'wb')
        pickle.dump(one_day, output)

    def load_one_day_from_file(self, file_path):
        with open(file_path, 'rb') as input:
            return pickle.load(input)

    def one_day_to_key_value(self, day, output_path=None, append=True):
        """Takes the fitbit connection, connects to Fitbit and retrieves
        intraday values for day.

        Day is in format: YYYY-MM-DD
        user_timezone is a pytz compatible string. If None, set to UTC

        TODO (ed): Should day just be in datetime.date format and we convert it
            for the api call?
        """
        user_timezone = pytz.timezone(self.user_profile['timezone'])

        if output_path:
            if append:
                out_file = open(output_path, 'a')
            else:
                out_file = open(output_path, 'w')
        else:
            out_file = None
        one_day = self.get_one_day(day)  # Uncomment to connect to Fitbit
    #    one_day = load_one_day_from_file('%s/%s' % (os.getcwd(),
    #                                     '2013-01-19.pk'))  # for dev

        date = datetime.datetime.strptime(day, '%Y-%m-%d')
        for minute in one_day['activities-steps-intraday']['dataset']:
            # Format: 2013-01-20T18:40:00-08:00
            time = datetime.datetime.strptime(minute['time'], "%H:%M:%S")
            dt = datetime.datetime.combine(date, time.time())
            dt_str = dt.replace(tzinfo=user_timezone).isoformat()
            logline = '%s, steps=%s' % (dt_str, minute['value'])
            if out_file:
                out_file.write("%s\n" % logline)
            else:
                logging.info(logline)
        if out_file:
            out_file.close()

    def get_last_sync_time(self):
        """Gets the most recent sync datetime

        Assuming only one device
        """
        devices = self.fb.get_devices()
        last_sync_dt = datetime.datetime.strptime(devices[0]['lastSyncTime'],
                                                  '%Y-%m-%dT%H:%M:%S.%f')
        self.last_sync = last_sync_dt
        return last_sync_dt

if __name__ == '__main__':
    # TODO(ed): What this should really be doing is:
    fbs = FitBitSplunk()
    fbs.login(fbs_settings.CONSUMER_KEY, fbs_settings.CONSUMER_SECRET,
              fbs_settings.USER_KEY, fbs_settings.USER_SECRET)
    # TODO(ed): Get the last device sync time
    fbs.get_last_sync_time()
    # TODO(ed): Compare to the last downloaded date
    # TODO(ed): Download all days between last downloaded date and last device
    #   sync time
    # TODO(ed): Do NOT download today's data to make it easy. But when we do
    #   want to make it hourly, we need to make sure we're appending to the
    #   file and not overwriting it
    # TODO(ed): Need to make a backfill script that will collect the user's
    #   history without going over the rate limit


    #my_day = get_one_day(fb, '2013-01-19')
    #save_one_day_to_file(my_day, '2013-01-19.pk')

    #user_profile = fb.user_profile_get()
    user_profile = pickle.load(open('user_profile.pk', 'rb'))  # For dev
    user_timezone = user_profile['user']['timezone']

#    fb = None #for development
#    one_day_to_key_value(fb, '2013-01-19', user_timezone)
    day_to_fetch = '2013-01-22'
    fbs.one_day_to_key_value(fb, day_to_fetch,
                             output_path=('%s.txt' % day_to_fetch),
                             user_timezone=user_timezone)
    exit()


#    one_day = load_one_day_from_file('%s/%s' % (os.getcwd(), '2013-01-19.pk'))
#    logging.info('Loaded one day')
#    summary = one_day['activities-steps'][0]
#    logging.info('Statistics for %s' % summary['dateTime'])
#    logging.info('Number of steps for the day: %s' % summary['value'])
#    logging.info('Minute by minute: %s' % one_day['activities-steps-intraday']['dataset'])
#    for minute in one_day['activities-steps-intraday']['dataset']:
#        logging.info('%s: %s' % (minute['time'], minute['value']))
    #user_profile = fb.user_profile_get()
    #logging.info('User profile: %s', user_profile)
    #friends = fb.get_friends()
    #logging.info('Friends: %s', friends)
#    for minute in one_day.activities-steps-intraday.dataset:
#        logging.info('%s: %s' % (minute.time, minute.value))
