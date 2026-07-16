import datetime

today_str = "MARZO 2026"
reinsp_override = "MARZO 2027"

hide_elab_day = False
hide_insp_day = False

today_date_part = today_str[:10]
if today_date_part.startswith("00/") or today_date_part.startswith("00-"):
    hide_elab_day = True
    today_str = "01" + today_str[2:]
elif today_date_part.endswith("-00"):
    hide_elab_day = True
    today_str = today_str[:7] + "-01" + today_str[10:]

reinsp_date_part = reinsp_override[:10]
if reinsp_date_part.startswith("00/") or reinsp_date_part.startswith("00-"):
    hide_insp_day = True
    reinsp_override = "01" + reinsp_override[2:]
elif reinsp_date_part.endswith("-00"):
    hide_insp_day = True
    reinsp_override = reinsp_override[:7] + "-01" + reinsp_override[10:]
elif not reinsp_override and hide_elab_day:
    hide_insp_day = True

try:
    dt = None
    if "-" in str(today_str):
        dt = datetime.datetime.strptime(today_str[:10], "%Y-%m-%d")
    elif "/" in str(today_str):
        parts = str(today_str[:10]).split("/")
        if len(parts) == 3:
            if len(parts[2]) == 4:
                dt = datetime.datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            elif len(parts[0]) == 4:
                dt = datetime.datetime(int(parts[0]), int(parts[1]), int(parts[2]))

    if dt:
        elab_date = dt.strftime("%d/%m/%Y")
        if reinsp_override:
            try:
                if "-" in str(reinsp_override):
                    rd = datetime.datetime.strptime(reinsp_override[:10], "%Y-%m-%d")
                else:
                    rd = datetime.datetime.strptime(reinsp_override[:10], "%d/%m/%Y")
                insp_date = rd.strftime("%d/%m/%Y")
            except Exception:
                insp_date = str(reinsp_override)
        else:
            try:
                insp_dt = dt.replace(year=dt.year + 1)
            except ValueError:
                insp_dt = dt.replace(year=dt.year + 1, day=28)
            insp_date = insp_dt.strftime("%d/%m/%Y")
    else:
        elab_date = today_str
        insp_date = reinsp_override if reinsp_override else "N/A"
except Exception as e:
    print("Exception occurred:", e)
    elab_date = today_str if today_str else datetime.date.today().strftime("%d/%m/%Y")
    insp_date = reinsp_override if reinsp_override else "N/A"

if hide_elab_day and elab_date.startswith("01/"):
    elab_date = elab_date[3:]
if hide_insp_day and insp_date.startswith("01/"):
    insp_date = insp_date[3:]

print(f"Result: elab_date='{elab_date}', insp_date='{insp_date}'")
