"""Static policy baselines used by the evaluation node."""

BASELINES = {
    "notice_period": "Standard Indian employment: 30-90 days. Flag if > 90 days.",
    "non_compete": "Beyond 1 year or national geographic scope is aggressive.",
    "lock_in": "Beyond 6 months for employment is above standard.",
    "ip_assignment": "Assigning IP created outside work hours on personal tools is a red flag.",
    "compensation": "Flag if variable pay > 40% of CTC without clear metrics.",
    "liability": "Unlimited personal liability clauses are high risk.",
}
