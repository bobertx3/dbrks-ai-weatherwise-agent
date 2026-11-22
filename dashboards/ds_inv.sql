SELECT i.site_name, s.site_type, i.state,
  CASE WHEN i.product_name ILIKE '%aortic valve%' THEN 'Aortic valve' WHEN i.product_name ILIKE '%stent%' THEN 'Coated stent'
       WHEN i.product_name ILIKE '%balloon%' THEN 'DCB catheter' WHEN i.product_name ILIKE '%fibrin%' THEN 'Fibrin sealant'
       WHEN i.product_name ILIKE '%bone allograft%' THEN 'Bone allograft' WHEN i.product_name ILIKE '%thrombin%' THEN 'Thrombin'
       WHEN i.product_name ILIKE '%cornea%' THEN 'Corneal graft' ELSE i.product_name END AS product,
  i.on_hand_qty AS on_hand
FROM inventory i LEFT JOIN sites s ON s.site_id = i.site_id
