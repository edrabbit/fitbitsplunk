import argparse
import datetime
import dateutil.rrule
import errno
import logging
import os
import pytz

import tailer

import fbs_settings
import fitbit

logging.basicConfig(level=logging.DEBUG)


class FitBitSplunk():

    def __init__(self):
        pass

    def get_user_keys(self, consumer_key, consumer_secret):
        logging.info('Processing OAuth keys...')
        client = fitbit.FitbitOauthClient(consumer_key, consumer_secret)

        # get request token
        token = client.fetch_request_token()
        print("Please go to this url in a browser to authorize: %s"
                    % client.authorize_token_url(token))
        verifier = raw_input('\nPlease enter your returned PIN: ')
        # get access token
        token = client.fetch_access_token(token, verifier)
        print('Here are your necessary credentials:')
        print('--user_key %s --user_secret %s' % (str(token.key),
                                                  str(token.secret)))

    def get_profile(self):
        user = self.fb.user_profile_get()
        self.user_profile = user['user']

    def get_join_date(self):
        if not self.user_profile:
            self.get_profile()
        dt = datetime.datetime.strptime(
            self.user_profile['memberSince'], '%Y-%m-%d')
        return dt

    def get_user_id(self):
        if not self.user_profile:
            self.get_profile()
        return self.user_profile['encodedId']

    def login(self, consumer_key, consumer_secret, user_key, user_secret,
              get_profile=True):
        fb = fitbit.Fitbit(consumer_key, consumer_secret,
                           user_key=user_key, user_secret=user_secret)
        self.fb = fb
        if get_profile:
            self.get_profile()

    def _dt_to_datestring(self, dt):
        if isinstance(dt, datetime.datetime):
            return dt.date().isoformat()

    def get_activity_summary_date_range(self, activity, start_date, end_date,
                                        format='json'):
        """See https://wiki.fitbit.com/display/API/API-Get-Time-Series for
         valid activities"""
        start_date = self._dt_to_datestring(start_date)
        end_date = self._dt_to_datestring(end_date)
        url = ('%s/%s/user/%s/activities/%s/date/%s/%s.%s'
               % (self.fb.API_ENDPOINT, self.fb.API_VERSION, '-',
               activity, start_date, end_date, format))
        summary = self.fb.make_request(url=url)
        return self._sort_summary_into_dates(
            summary['activities-%s' % activity])

    def _sort_summary_into_dates(self, summary):
        # Summary is a list, make sure dates are in order
        foo = {}
        for x in summary:
            foo[x['dateTime']] = x['value']
        return foo

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
        one_day = self.get_one_day(day)

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

    def get_last_log_date(self, logfile):
        if not os.path.exists(logfile):
            return None
        last_line = tailer.tail(open(logfile), 1)
        if last_line:
            last_line = last_line[0]
            return last_line.split(', ')[0].split('T')[0]
        else:
            return None


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Fetch Fitbit data via API')
    parser.add_argument('--user_key', type=str, help='Your user key',
                        default=fbs_settings.USER_KEY)
    parser.add_argument('--user_secret', type=str, help='Your secret key',
                        default=fbs_settings.USER_SECRET)
    parser.add_argument('--consumer_key', type=str, help='App consumer key',
                        default=fbs_settings.CONSUMER_KEY)
    parser.add_argument('--consumer_secret', type=str,
                        help='App consumer secret',
                        default=fbs_settings.CONSUMER_SECRET)
    parser.add_argument('--output', type=str, help='Output filepath',
                        default='./output.log')
    parser.add_argument('--start_date', type=str, help='Date to start')
    parser.add_argument('--end_date', type=str, help='Date to stop')
    parser.add_argument('--get_user_keys', action='store_true',
                        help='Just fetch user keys. aka Poor Man\'s OAuth')
    args = parser.parse_args()


    fbs = FitBitSplunk()
    if args.get_user_keys:
        if not args.consumer_key or not args.consumer_secret:
            print('ERROR: Consumer Key and Consumer Secret are required in '
                  'order to fetch user key/secret.\n'
                  'They can be retrieved from: https://dev.fitbit.com/apps\n'
                  'Exiting')
            exit(errno.EINVAL)
        fbs.get_user_keys(args.consumer_key, args.consumer_secret)
        exit()

    if not args.user_key or not args.user_secret:
        print('ERROR: User Key and User Secret are required. Exiting.')
        parser.print_help()
        exit(errno.EINVAL)

    fbs.login(args.consumer_key, args.consumer_secret,
              args.user_key, args.user_secret)
    user_id = fbs.get_user_id()

    # TODO(ed): Modify these based on sync date or assume user knows best?
    # If a start or end date is not specified, use Fitbit's memberSince
    # date and last sync date respectively

    last_sync = fbs.get_last_sync_time()
    logging.debug('last sync time was %s' % last_sync)

    if not args.start_date:
        last_log_date = fbs.get_last_log_date(args.output)
        if last_log_date:
            start_date = datetime.datetime.strptime(last_log_date, '%Y-%m-%d')
            start_date = start_date + datetime.timedelta(days=1)
            logging.debug('last log date=%s' % last_log_date)
        else:
            start_date = fbs.get_join_date()
    else:
        start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d')

    if not args.end_date:
        end_date = last_sync - datetime.timedelta(days=1)
    else:
        end_date = datetime.datetime.strptime(args.end_date, '%Y-%m-%d')
        if end_date > last_sync:
            logging.debug(
                'Provided end_date is later than last sync date, '
                'using last sync date instead')
            end_date = last_sync - datetime.timedelta(days=1)

    logging.debug('start_date=%s, end_date=%s' % (start_date, end_date))
    if start_date > end_date:
        logging.debug(
            'start date is after end date, meaning we are up to date')
        exit()

    fh = open(args.output, 'a+')

    summary = {}
    # leaving out floors and elevation here because I don't have it
    activities = [
        'calories', 'steps', 'distance',
        'minutesSedentary', 'minutesLightlyActive',
        'minutesFairlyActive', 'minutesVeryActive', 'activityCalories']

    # Note: This will make len(activities) API calls
    for activity in activities:
        summary[activity] = fbs.get_activity_summary_date_range(activity,
                                                                start_date,
                                                                end_date)

    for dt in dateutil.rrule.rrule(dateutil.rrule.DAILY,
                                   dtstart=start_date, until=end_date):
        day = dt.date().isoformat()

        # Log it as the microsecond before midnight since that's the end of day
        logdate = datetime.datetime.combine(dt.date(), datetime.time.max)
        logdate = logdate.isoformat()
        logline = '%s, encodedId=%s' % (logdate, user_id)
        for activity in activities:
            logline = '%s, %s=%s' % (logline, activity, summary[activity][day])
        logging.debug(logline)
        fh.write(logline + '\n')

    fh.close()
    exit()
