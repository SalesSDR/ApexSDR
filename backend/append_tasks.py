async def execute_email_dispatch_task(ctx, prospect_id: str):
    """
    Directly generates and dispatches an email, ignoring LinkedIn.
    """
    sessionmaker = ctx['sessionmaker']
    unipile = ctx['unipile_client']
    redis = ctx['redis']

    async with sessionmaker() as db:
        p_res = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
        prospect = p_res.scalar_one_or_none()
        if not prospect:
            return

        if not prospect.email:
            logger.error(f"Cannot dispatch email for {prospect_id}: Missing email address")
            await StateMachine.transition(db=db, redis=redis, prospect_id=prospect_id, new_state="EMAIL_FAILED", event_trigger="Missing Email")
            await db.commit()
            return
            
        try:
            ai_message = await generate_ai_message(prospect, prompt_type="email", sequence=1)
            if "ApexSDR" not in ai_message:
                ai_message += "\n\nSent via ApexSDR"
                
            email_account_id = settings.UNIPILE_EMAIL_ACCOUNT_ID
            
            if email_account_id:
                api_res = await unipile.send_email(
                    account_id=email_account_id,
                    recipient=prospect.email,
                    subject="ApexSDR Outreach",
                    text=ai_message
                )
            else:
                from app.services.email import send_native_email
                api_res = await send_native_email(
                    recipient=prospect.email,
                    subject="ApexSDR Outreach",
                    text=ai_message
                )
                
            logger.info(f"Email dispatch success for {prospect_id}: {api_res}")
            
            await StateMachine.transition(
                db=db,
                redis=redis,
                prospect_id=prospect_id,
                new_state="EMAIL_SENT",
                event_trigger="Bypass Email Dispatch",
                payload_updates={
                    "linkedin_step_count": 0,
                    "email_step_count": 1,
                    "last_message_sent_at": datetime.utcnow().isoformat(),
                    "reply_received": False
                }
            )
            await db.commit()
            
        except Exception as e:
            logger.error(f"Email dispatch failed for {prospect_id}: {e}")
            await StateMachine.transition(db=db, redis=redis, prospect_id=prospect_id, new_state="EMAIL_FAILED", event_trigger=f"Dispatch Error: {e}")
            await db.commit()
