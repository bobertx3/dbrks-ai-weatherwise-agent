SELECT shipment_id, product_name,
  CASE WHEN product_name ILIKE '%aortic valve%' THEN 'Aortic valve' WHEN product_name ILIKE '%stent%' THEN 'Coated stent'
       WHEN product_name ILIKE '%balloon%' THEN 'DCB catheter' WHEN product_name ILIKE '%fibrin%' THEN 'Fibrin sealant'
       WHEN product_name ILIKE '%bone allograft%' THEN 'Bone allograft' WHEN product_name ILIKE '%thrombin%' THEN 'Thrombin'
       WHEN product_name ILIKE '%cornea%' THEN 'Corneal graft' ELSE product_name END AS product,
  status, priority, carrier, origin, destination, destination_facility_name AS facility, destination_facility_type AS facility_type,
  split(destination, ', ')[1] AS dest_state, destination_latitude AS lat, destination_longitude AS lon,
  CAST(eta_date AS DATE) AS eta_date,
  COALESCE(delay_hours, 0) AS delay_hours, delay_reason,
  CASE WHEN COALESCE(delay_hours, 0) = 0 THEN 'On time'
       WHEN delay_reason RLIKE '(?i)snow|storm|rain|atmospheric|thunder' THEN 'Weather'
       WHEN delay_reason RLIKE '(?i)dock' THEN 'Dock hold'
       WHEN delay_reason RLIKE '(?i)dry-ice|reefer' THEN 'Equipment'
       WHEN delay_reason RLIKE '(?i)document' THEN 'Paperwork'
       ELSE 'Carrier & network' END AS delay_cause,
  last_recorded_temp_f AS sensor_f, temperature_min_f AS min_f, temperature_max_f AS max_f,
  CASE WHEN last_recorded_temp_f > temperature_max_f THEN 'Too warm'
       WHEN last_recorded_temp_f < temperature_min_f THEN 'Too cold' ELSE 'In range' END AS temp_status,
  CASE WHEN status <> 'Delivered' THEN 1 ELSE 0 END AS is_active,
  CASE WHEN status <> 'Delivered' AND status = 'Delayed' THEN 1 ELSE 0 END AS is_delayed,
  CASE WHEN status <> 'Delivered' AND (last_recorded_temp_f > temperature_max_f OR last_recorded_temp_f < temperature_min_f) THEN 1 ELSE 0 END AS is_excursion,
  CASE WHEN status = 'Delayed' AND delay_reason RLIKE '(?i)snow|storm|rain|atmospheric|thunder' THEN 1 ELSE 0 END AS is_weather_delay
FROM shipments
