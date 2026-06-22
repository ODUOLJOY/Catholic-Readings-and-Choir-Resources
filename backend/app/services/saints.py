from datetime import datetime


SAINTS = {
    "01-01": "Mary, Mother of God",
    "02-14": "Saints Cyril and Methodius",
    "03-19": "Saint Joseph",
    "06-29": "Saints Peter and Paul",
    "08-15": "Assumption of Mary",
    "11-01": "All Saints",
    "12-25": "Nativity of the Lord"
}


def get_today_saint():

    today = datetime.now().strftime("%m-%d")

    saint = SAINTS.get(
        today,
        "Saint of the Day"
    )

    return {
        "date": today,
        "saint": saint
    }