# Daily Email Scheduler

This scheduler script (`daily_email_scheduler.py`) will automatically run your email campaign every day at **6:00 AM IST (Indian Standard Time)**. It logs the start and end time of each campaign run for auditing purposes.

## Features
- Runs your email campaign once every 24 hours at 6:00 AM IST
- Logs the start and end time (with date) of each run to `scheduler_audit.log`
- Automatically repeats every day

## Setup
1. **Install dependencies:**
   - Make sure you have Python 3.x installed.
   - Install `pytz` if not already:
     ```bash
     pip install pytz
     ```
2. **Place the script:**
   - Ensure `daily_email_scheduler.py` is in your project root (or wherever you want to run it from).
   - The script expects your campaign to be runnable with:
     ```bash
     python src/main.py --resume data/Ayush.pdf --batch-size 20 --daily-limit 20
     ```
     from the `AutoEmailer/CV_Autorun` directory. Adjust the command in the script if your setup is different.

## Usage
Run the scheduler with:
```bash
python daily_email_scheduler.py
```
- The script will wait until the next 6:00 AM IST, run your campaign, and repeat every day.
- You can stop the script at any time with `Ctrl+C`.

## Log File
- The script creates/updates a file called `scheduler_audit.log` in the same directory.
- Each run will append two lines:
  - When the campaign starts: `YYYY-MM-DD HH:MM:SS - Campaign STARTED`
  - When the campaign ends:   `YYYY-MM-DD HH:MM:SS - Campaign ENDED`

## Customization
- To change the scheduled time, edit the `hour` and `minute` in the `seconds_until_next_6am_ist()` function in the script.
- To change the campaign command, edit the `run_campaign()` function.

## Notes
- Make sure your campaign script and all dependencies are working before relying on the scheduler.
- The scheduler must remain running (do not close the terminal) for the automation to work.

---

**For any issues or customizations, edit `daily_email_scheduler.py` as needed!** 