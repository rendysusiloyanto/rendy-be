import datetime


def timestamp_to_datetime(ts):
    return datetime.datetime.fromtimestamp(ts)


def humanize_datetime(dt):
    return dt.strftime("%d %B %Y, %H:%M:%S")
