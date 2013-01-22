import argparse
import datetime
import logging
import time

import fbs_settings
import fitbitsplunk

output_dir = 'data'

parser = argparse.ArgumentParser(description='Fetch FitBit intraday data')
parser.add_argument('start_date')
parser.add_argument('end_date')
parser.add_argument('delay', type=int)
parser.add_argument('--outfile', type=str, required=False)

args = parser.parse_args()

if args.outfile:
    outfile = args.outfile
else:
    outfile = '%s/%s-%s.log' % (output_dir,
                                args.start_date.replace('-',''),
                                args.end_date.replace('-',''))

start_date = datetime.datetime.strptime(args.start_date, '%Y-%m-%d')
end_date = datetime.datetime.strptime(args.end_date, '%Y-%m-%d')
delay = args.delay

day_count = (end_date - start_date).days + 1

fbs = fitbitsplunk.FitBitSplunk()

for single_date in (start_date + datetime.timedelta(n) for n in range(day_count)):
    day = single_date.strftime('%Y-%m-%d')
    logging.debug('Downloading data for %s...' % day)
    try:
        fbs.login(fbs_settings.CONSUMER_KEY, fbs_settings.CONSUMER_SECRET,
                  fbs_settings.USER_KEY, fbs_settings.USER_SECRET)
        #fbs.one_day_to_key_value(day, ('%s/%s.log' % (output_dir, day)))
        fbs.one_day_to_key_value(day, outfile, append=True)
        # Sleep for a conservative 1 minute to avoid going over API limits
        logging.info('Downloaded data for %s' % day)
    except:
        logging.error('Failed to retrieve %s' % day)
        raise
    try:
        logging.debug('Sleeping for %s seconds' % delay)
        time.sleep(delay)
    except KeyboardInterrupt:
        logging.error('User cancelled after downloading %s' % day)
