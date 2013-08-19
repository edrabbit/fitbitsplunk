import argparse
import datetime
import dateutil.rrule
import json
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

    def get_multi_days(self,start_day, end_day):
        """ start_day and end_day are strings right now
        """
        # TODO(ed): For some reason this is returning activities instead of minute by minute info
        url = ('%s/%s/user/%s/activities/steps/date/%s/%s/1m/00:00:00/00:00:00.json' %
               (self.fb.API_ENDPOINT, self.fb.API_VERSION, '-',
                start_day, end_day))
        multi_days = self.fb.make_request(url=url)
        return multi_days

    def get_one_day(self, day):
        if isinstance(day, datetime.date):
            day = day.isoformat()
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

        date = day.isoformat()
        log_day = []
        for minute in one_day['activities-steps-intraday']['dataset']:
            # Format: 2013-01-20T18:40:00-08:00
            time = datetime.datetime.strptime(minute['time'], "%H:%M:%S")
            dt = datetime.datetime.combine(day, time.time())
            dt_str = dt.replace(tzinfo=user_timezone).isoformat()
            logline = '%s, steps=%s' % (dt_str, minute['value'])
            if out_file:
                out_file.write("%s\n" % logline)
            else:
                log_day.append(logline)
                logging.info(logline)
        if out_file:
            out_file.close()
        return log_day

    def get_last_sync_time(self):
        """Gets the most recent sync datetime

        Assuming only one device
        """
        devices = self.fb.get_devices()
        last_sync_dt = datetime.datetime.strptime(devices[0]['lastSyncTime'],
                                                  '%Y-%m-%dT%H:%M:%S.%f')
        self.last_sync = last_sync_dt
        return last_sync_dt

    def load_last_download_time(self, filepath):
        try:
            f = open(filepath, 'r')
        except IOError:
            return None
        last_download = f.read()
        ld_dt = datetime.datetime.strptime(last_download, '%Y-%m-%d %H:%M:%S.%f')
        return ld_dt

    def write_last_download_time(self, filepath, dl_time):
        """dl_time is a datetime object
        """
        f = open(filepath, 'w+')
        f.write(dl_time.strftime('%Y-%m-%d %H:%m:%S.%f'))
        f.close()





if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Fetch Fitbit data via API')
    parser.add_argument('--user_key', type=str, help='Your user key', default=fbs_settings.USER_KEY)
    parser.add_argument('--user_secret', type=str, help='Your secret key', default=fbs_settings.USER_SECRET)
    parser.add_argument('--consumer_key', type=str, help='App consumer key', default=fbs_settings.CONSUMER_KEY)
    parser.add_argument('--consumer_secret', type=str, help='App consumer secret', default=fbs_settings.CONSUMER_SECRET)
    parser.add_argument('--output', type=str, help='Output filepath', default='./output.log')
    parser.add_argument('--start_date', type=str, help='Date to start')
    parser.add_argument('--end_date', type=str, help='Date to stop')
    parser.add_argument('--format', type=str, help='Format to output [kv, json]', default='kv')
    args = parser.parse_args()

    fbs = FitBitSplunk()
    #fbs.login(fbs_settings.CONSUMER_KEY, fbs_settings.CONSUMER_SECRET,
    #          fbs_settings.USER_KEY, fbs_settings.USER_SECRET)
    fbs.login(args.consumer_key, args.consumer_secret, args.user_key, args.user_secret)

    if not args.start_date:
        # Get the last device sync time (datetime)
        last_dl = fbs.load_last_download_time(fbs_settings.DL_MARKER)
        if last_dl:
            download_date_start = last_dl
        else:  # If no record of download, start from the beginning
            download_date_start = datetime.datetime.strptime(fbs.user_profile['memberSince'], '%Y-%m-%d')
    else:
        download_date_start = datetime.datetime.strptime(args.start_date, '%Y-%m-%d')

    if not args.end_date:
        last_sync = fbs.get_last_sync_time()
        download_date_end = last_sync - datetime.timedelta(days=1)
    else:
        download_date_end = datetime.datetime.strptime(args.end_date, '%Y-%m-%d')

    if download_date_start.date() == download_date_end.date():
        logging.debug('Start and end date are equal, wait for a new sync')
        exit()

    fh = open(args.output, 'a')
    for dt in dateutil.rrule.rrule(dateutil.rrule.DAILY,
                                   dtstart=download_date_start,
                                   until=download_date_end):
        logging.debug('fetching data for %s' % dt.date())

        if args.format == 'kv':
            one_day = fbs.one_day_to_key_value(dt.date())
            for minute in one_day:
                fh.write(minute + '\n')
        else:
            one_day = fbs.get_one_day(dt.date())
            logging.debug('%s: %s', dt.date(), one_day)
            fh.write(str(one_day) + '\n')

    fbs.write_last_download_time(fbs_settings.DL_MARKER, download_date_end)

    exit()