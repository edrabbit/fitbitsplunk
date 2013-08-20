fitbitsplunk
============

Get your Fitbit data into Splunk.

Will gather data from your Fitbit account and log it as such:

    2013-08-19T23:59:59.999999, encodedId=2223TS, calories=1959, steps=3579, distance=2.73646, minutesSedentary=1331, minutesLightlyActive=49, minutesFairlyActive=57, minutesVeryActive=3, activityCalories=424

This is still very much a work in progress. Pardon the cruft. The "intraday"
branch is attempts at doing minute resolution but requires access to the
Fitbit Partner API, which is available upon request.

Requirements
-------------
Uses python-fitbit library
https://github.com/orcasgit/python-fitbit
http://pypi.python.org/pypi/fitbit/0.0.2


### Quick pips:
    pip install fitbit
    pip install python-dateutil
    pip install pytz
    pip install tailer
