from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
import uuid
import base64
from datetime import datetime
from mailer import send_email

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///phishguard.db"

db = SQLAlchemy(app)

RED_FLAGS = {
    "it_password_reset": [
        "The sender created false urgency (\"expires in 24 hours\") — a classic pressure tactic to stop you thinking clearly.",
        "It asked you to click a link to \"verify your identity\" — legitimate IT teams never ask you to confirm credentials via an emailed link.",
        "The greeting used your first name generically, with no other personal or account-specific detail a real system would include.",
        "Hovering over the button would have shown a link that didn't match your company's actual domain."
    ]
}

TRANSPARENT_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBTAA7"
)


class Target(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)


class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    template_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), unique=True)
    target_id = db.Column(db.Integer, db.ForeignKey("target.id"), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaign.id"), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)  # "sent", "opened", "clicked"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    target = db.relationship("Target", backref="events")
    campaign = db.relationship("Campaign", backref="events")


@app.route("/")
def home():
    return "PhishGuard is alive"


@app.route("/preview-email")
def preview_email():
    event = Event.query.filter_by(event_type="sent").first()
    token = event.token
    tracking_link = f"http://127.0.0.1:5000/click/{token}"
    pixel_url = f"http://127.0.0.1:5000/pixel/{token}"

    return render_template(
        "emails/it_password_reset.html",
        target_name=event.target.name,
        tracking_link=tracking_link,
        pixel_url=pixel_url
    )


@app.route("/click/<token>")
def click(token):
    event = Event.query.filter_by(token=token).first()

    if event is None:
        return "Invalid or expired link.", 404

    click_event = Event(
        target_id=event.target_id,
        campaign_id=event.campaign_id,
        event_type="clicked"
    )
    db.session.add(click_event)
    db.session.commit()

    template_name = event.campaign.template_name
    flags = RED_FLAGS.get(template_name, ["This email showed signs of phishing."])

    return render_template(
        "awareness.html",
        target_name=event.target.name,
        red_flags=flags
    )


@app.route("/pixel/<token>")
def pixel(token):
    event = Event.query.filter_by(token=token).first()

    if event is not None:
        open_event = Event(
            target_id=event.target_id,
            campaign_id=event.campaign_id,
            event_type="opened"
        )
        db.session.add(open_event)
        db.session.commit()

    return TRANSPARENT_PIXEL, 200, {"Content-Type": "image/gif"}


@app.route("/new-campaign")
def new_campaign():
    return render_template("new_campaign.html")


@app.route("/create-campaign", methods=["POST"])
def create_campaign():
    campaign_name = request.form["campaign_name"]
    raw_targets = request.form["targets"]

    campaign = Campaign(name=campaign_name, template_name="it_password_reset")
    db.session.add(campaign)
    db.session.commit()

    sent_count = 0

    for line in raw_targets.strip().split("\n"):
        if "," not in line:
            continue
        name, email = line.split(",", 1)
        name = name.strip()
        email = email.strip()

        existing = Target.query.filter_by(email=email).first()
        if existing:
            target = existing
        else:
            target = Target(name=name, email=email)
            db.session.add(target)
            db.session.commit()

        sent_event = Event(
            target_id=target.id,
            campaign_id=campaign.id,
            event_type="sent"
        )
        db.session.add(sent_event)
        db.session.commit()

        tracking_link = f"http://127.0.0.1:5000/click/{sent_event.token}"
        pixel_url = f"http://127.0.0.1:5000/pixel/{sent_event.token}"

        html_body = render_template(
            "emails/it_password_reset.html",
            target_name=target.name,
            tracking_link=tracking_link,
            pixel_url=pixel_url
        )

        send_email(
            to_address=target.email,
            subject="Action required: verify your account",
            html_body=html_body
        )
        sent_count += 1

    return f"Campaign '{campaign_name}' launched. {sent_count} emails sent."


@app.route("/dashboard")
def dashboard():
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()

    campaign_stats = []
    for c in campaigns:
        sent = db.session.query(Event.target_id).filter_by(campaign_id=c.id, event_type="sent").distinct().count()
        opened = db.session.query(Event.target_id).filter_by(campaign_id=c.id, event_type="opened").distinct().count()
        clicked = db.session.query(Event.target_id).filter_by(campaign_id=c.id, event_type="clicked").distinct().count()
        click_rate = round((clicked / sent) * 100) if sent > 0 else 0

        campaign_stats.append({
            "id": c.id,
            "name": c.name,
            "created_at": c.created_at.strftime("%b %d, %Y"),
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "click_rate": click_rate
        })

    total_sent = sum(c["sent"] for c in campaign_stats)
    total_clicked = sum(c["clicked"] for c in campaign_stats)
    overall_rate = round((total_clicked / total_sent) * 100) if total_sent > 0 else 0

    return render_template(
        "dashboard.html",
        campaigns=campaign_stats,
        total_sent=total_sent,
        total_clicked=total_clicked,
        overall_rate=overall_rate
    )


if __name__ == "__main__":
    app.run(debug=True)