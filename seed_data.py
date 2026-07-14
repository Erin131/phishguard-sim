from app import app, db, Target, Campaign, Event

with app.app_context():
    # Create a target (a person being simulated-phished)
    target = Target(name="Erin", email="erin@example.com")
    db.session.add(target)

    # Create a campaign
    campaign = Campaign(name="Q1 IT Password Reset Test", template_name="it_password_reset")
    db.session.add(campaign)

    db.session.commit()  # commit here so target.id and campaign.id get assigned

    # Create a "sent" event with a real generated token
    event = Event(
        target_id=target.id,
        campaign_id=campaign.id,
        event_type="sent"
    )
    db.session.add(event)
    db.session.commit()

    print(f"Target created: {target.name} (id={target.id})")
    print(f"Campaign created: {campaign.name} (id={campaign.id})")
    print(f"Event token generated: {event.token}")