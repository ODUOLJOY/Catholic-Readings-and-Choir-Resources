from datetime import datetime


def get_year_cycle():
    year = datetime.now().year

    cycle = year % 3

    if cycle == 0:
        return "A"

    if cycle == 1:
        return "B"

    return "C"


def get_liturgical_season():
    month = datetime.now().month

    if month in [11, 12]:
        return "Advent"

    if month in [1]:
        return "Christmas"

    if month in [2, 3]:
        return "Lent"

    if month in [4, 5]:
        return "Easter"

    return "Ordinary Time"


def get_today_missal():

    return {
        "year": get_year_cycle(),

        "season": get_liturgical_season(),

        "readings": {
            "first": "Isaiah 55:1-11",

            "psalm": "Psalm 34",

            "second": "Romans 8:18-23",

            "gospel": "Matthew 13:1-23"
        }
    }