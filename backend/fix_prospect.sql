UPDATE workflow_states SET state = 'CONNECTION_ACCEPTED', payload = payload || '{"linkedin_accepted": true}'::jsonb WHERE prospect_id = 'dff9ef21-75fb-4245-9cf5-a74c6c879eea';
SELECT state, payload FROM workflow_states WHERE prospect_id = 'dff9ef21-75fb-4245-9cf5-a74c6c879eea';
