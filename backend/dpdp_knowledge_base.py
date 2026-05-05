"""
DPDP Act 2023 Knowledge Base
Structured sections for retrieval-augmented compliance analysis.
Each section contains a citation, title, and detailed legal text + obligations.
"""

DPDP_SECTIONS = [
    {
        "id": "DPDP Section 4",
        "title": "Grounds for Processing Personal Data",
        "text": """A Data Fiduciary may process personal data only where:
(a) the Data Principal has given consent for the processing of personal data for the purpose specified;
(b) the processing is necessary for performance of any function under any law, or for compliance with any judgment or order of any Court or Tribunal;
(c) for employment-related purposes including termination;
(d) for medical treatment or health services during an epidemic or natural disaster;
(e) for reasons of public interest in relation to the safety or security of the State, or for detection of fraud or any unlawful activity.

Compliance Obligation: The privacy policy must clearly specify the legal basis for processing personal data, with explicit consent being the primary mechanism for non-exempt processing.""",
    },
    {
        "id": "DPDP Section 5",
        "title": "Notice to Data Principal",
        "text": """Before obtaining consent, the Data Fiduciary must provide notice to the Data Principal containing:
(a) description of personal data collected and purpose of processing;
(b) manner of exercise of rights under Chapter III;
(c) procedure for grievance redressal;
(d) description of the grievance redressal mechanism;
(e) contact details of Data Protection Officer or person responsible for grievance redressal;
(f) right to access personal data and summary of processing activities;
(g) right to correction and erasure of personal data;
(h) any other information prescribed by the Board.

Compliance Obligation: The privacy policy must contain a comprehensive notice that clearly describes what data is collected, why it is collected, how rights can be exercised, and who to contact.""",
    },
    {
        "id": "DPDP Section 6",
        "title": "Consent",
        "text": """Consent must be:
(a) free, specific, informed, unconditional, and unambiguous;
(b) given by a clear affirmative action;
(c) clearly indicating the Data Principal's wishes;
(d) limited to the purpose for which it is sought;
(e) capable of being withdrawn at any time with the same ease as it was given.

The request for consent must be presented in a clear and plain language, and the Data Principal must have the right to access basic information in English or any language specified in the Eighth Schedule to the Constitution.

Compliance Obligation: Privacy policies must demonstrate free, specific, informed, and unambiguous consent mechanisms with easy withdrawal procedures. Consent language must be clear and plain, not buried in legalese.""",
    },
    {
        "id": "DPDP Section 6(5)",
        "title": "Consent for Specific Purposes Only",
        "text": """Where consent is given for a specific purpose, the Data Fiduciary may process personal data only for that specific purpose. Processing for any purpose not compatible with the original purpose is prohibited unless fresh consent is obtained.

Compliance Obligation: Privacy policies must clearly specify the exact purpose for which data is collected and prohibit use for unrelated purposes. Purpose limitation must be enforced.""",
    },
    {
        "id": "DPDP Section 7",
        "title": "Consent Managers",
        "text": """A Data Principal may give, manage, review, or withdraw consent through a Consent Manager. Consent Managers shall be registered with the Data Protection Board and act as agents of the Data Principal.

Compliance Obligation: Where a Consent Manager is used, the privacy policy must identify the Consent Manager and explain the Data Principal's right to use one.""",
    },
    {
        "id": "DPDP Section 8(1)",
        "title": "Right to Access Personal Data",
        "text": """Every Data Principal shall have the right to obtain from the Data Fiduciary:
(a) confirmation that the Data Fiduciary is processing or has processed personal data of the Data Principal;
(b) a summary of the personal data being processed or that has been processed;
(c) a brief summary of the processing activities undertaken by the Data Fiduciary with respect to the personal data of the Data Principal.

Compliance Obligation: Privacy policies must describe how Data Principals can access their data and obtain summaries of processing activities.""",
    },
    {
        "id": "DPDP Section 8(6)",
        "title": "Right to Erasure (Deletion) of Personal Data",
        "text": """The Data Principal shall have the right to request erasure of personal data when:
(a) the personal data is no longer necessary for the purpose for which it was collected;
(b) the Data Principal has withdrawn consent;
(c) the personal data has been unlawfully processed;
(d) the personal data has to be erased for compliance with any law.

The Data Fiduciary must erase the personal data within a reasonable time after receiving the request.

Compliance Obligation: Privacy policies must clearly explain the right to data deletion/erasure and the process for requesting it, including reasonable timelines.""",
    },
    {
        "id": "DPDP Section 8(7)",
        "title": "Right to Nomination",
        "text": """The Data Principal shall have the right to nominate any other individual who shall, in the event of the death or incapacity of the Data Principal, exercise the rights of the Data Principal under this Act.

Compliance Obligation: Privacy policies must inform Data Principals of their right to nominate a representative and describe the nomination process.""",
    },
    {
        "id": "DPDP Section 8(8)",
        "title": "Right to Grievance Redressal",
        "text": """The Data Principal shall have the right to have readily available means of registering a grievance with the Data Fiduciary regarding the processing of personal data. The Data Fiduciary must respond to grievances within a prescribed period.

Compliance Obligation: Privacy policies must describe the grievance redressal mechanism, including how to file complaints, response timelines, and escalation paths to the Data Protection Board of India.""",
    },
    {
        "id": "DPDP Section 9",
        "title": "Processing of Personal Data of Children and Persons with Disability",
        "text": """A Data Fiduciary may process personal data of a child (defined as a person below 18 years) only with verifiable consent of the parent or lawful guardian. The Data Fiduciary must not undertake tracking or behavioral monitoring of children or targeted advertising directed at children.

The Data Fiduciary must ensure that processing does not cause any detrimental effect on the well-being of a child.

Compliance Obligation: Privacy policies must have explicit child-protection provisions, parental consent mechanisms, and prohibitions on child tracking and targeted advertising to minors.""",
    },
    {
        "id": "DPDP Section 10",
        "title": "Additional Safeguards for Children",
        "text": """The Data Fiduciary must implement appropriate technical and organisational measures to ensure that personal data of children is processed with enhanced protection. No entity shall cause any detrimental effect on the well-being of a child through data processing.

Compliance Obligation: Privacy policies must specify enhanced safeguards for children's data and demonstrate child-safe data practices.""",
    },
    {
        "id": "DPDP Section 11",
        "title": "Rights and Duties of Data Principal",
        "text": """Every Data Principal has duties to:
(a) not register false or frivolous grievances or complaints;
(b) not impersonate another person;
(c) not suppress material information when providing personal data;
(d) not furnish any false particulars.

Non-compliance with these duties may result in suspension of rights.

Compliance Obligation: Privacy policies should include a section on Data Principal duties and the consequences of providing false information.""",
    },
    {
        "id": "DPDP Section 12",
        "title": "Accuracy of Personal Data",
        "text": """A Data Fiduciary must ensure that the personal data processed is complete, accurate, and kept up to date. The Data Fiduciary must take reasonable steps to ensure the quality of personal data.

Compliance Obligation: Privacy policies must describe mechanisms for Data Principals to correct or update their personal data and the Data Fiduciary's obligation to maintain data accuracy.""",
    },
    {
        "id": "DPDP Section 13",
        "title": "Data Retention and Deletion",
        "text": """The Data Fiduciary must not retain personal data beyond the period necessary to satisfy the purpose for which it is processed. Once the purpose is served, the personal data must be erased in a manner and form as may be prescribed. Retention may be extended only where necessary for compliance with law or for ongoing legal proceedings.

Compliance Obligation: Privacy policies must specify data retention periods for each category of personal data and describe the deletion procedure. Data must not be retained indefinitely.""",
    },
    {
        "id": "DPDP Section 14",
        "title": "Reasonable Security Safeguards",
        "text": """The Data Fiduciary must implement reasonable security safeguards to prevent personal data breach. The safeguards must be proportionate to the nature and volume of personal data processed, the risk of harm to the Data Principal, and the state of the art.

In the event of a personal data breach, the Data Fiduciary must notify the Data Protection Board and each affected Data Principal.

Compliance Obligation: Privacy policies must describe the security measures implemented (encryption, access controls, etc.) and the breach notification procedure.""",
    },
    {
        "id": "DPDP Section 15",
        "title": "Data Protection Officer (DPO)",
        "text": """Certain Significant Data Fiduciaries (or as notified by the Central Government) must appoint a Data Protection Officer. The DPO must be based in India and be the point of contact for grievance redressal.

The DPO's details must be published and prominently displayed.

Compliance Obligation: Where applicable, privacy policies must identify the Data Protection Officer by name (or title), provide contact details, and state that the DPO is based in India.""",
    },
    {
        "id": "DPDP Section 16",
        "title": "Significant Data Fiduciaries",
        "text": """The Central Government may notify certain Data Fiduciaries as Significant Data Fiduciaries based on:
(a) volume and sensitivity of personal data processed;
(b) risk of harm to Data Principals;
(c) potential impact on the sovereignty and integrity of India;
(d) security of the State; and
(e) public order.

Significant Data Fiduciaries have additional obligations including DPO appointment, independent data auditor, and Data Protection Impact Assessment.

Compliance Obligation: Significant Data Fiduciaries must state their classification and describe enhanced compliance measures in their privacy policies.""",
    },
    {
        "id": "DPDP Section 17",
        "title": "Data Protection Impact Assessment (DPIA)",
        "text": """Significant Data Fiduciaries must conduct a Data Protection Impact Assessment for processing that involves:
(a) systematic and extensive evaluation of personal aspects relating to Data Principals;
(b) large-scale processing of sensitive personal data;
(c) use of new or unproven technologies;
(d) any other processing that poses a significant risk of harm.

The DPIA must be reviewed periodically.

Compliance Obligation: Where a DPIA is required, the privacy policy should reference it and describe the risk assessment process.""",
    },
    {
        "id": "DPDP Section 18",
        "title": "Independent Data Auditor",
        "text": """Significant Data Fiduciaries must appoint an independent data auditor to evaluate compliance with this Act. The auditor must be registered with the Data Protection Board.

Compliance Obligation: Significant Data Fiduciaries must disclose the appointment of an independent data auditor in their privacy policy.""",
    },
    {
        "id": "DPDP Section 19",
        "title": "Processing in Public Interest",
        "text": """The Central Government may exempt certain processing activities from certain provisions of this Act for reasons of:
(a) sovereignty and integrity of India;
(b) security of the State;
(c) friendly relations with foreign States;
(d) maintenance of public order;
(e) prevention of incitement to any cognizable offence.

Compliance Obligation: If relying on a public interest exemption, the privacy policy must identify the applicable exemption and legal basis.""",
    },
    {
        "id": "DPDP Section 25",
        "title": "Cross-Border Transfer of Personal Data",
        "text": """The Central Government may, after an assessment of factors including necessary security and strategic interests of the State, notify countries or territories outside India to which a Data Fiduciary may transfer personal data. Until such notification, personal data may be transferred to countries that the Central Government has determined to provide an adequate level of protection.

Compliance Obligation: Privacy policies must disclose if personal data is transferred outside India, identify the destination countries, and state the legal basis for cross-border transfers.""",
    },
    {
        "id": "DPDP Section 26",
        "title": "Exemptions for Government Agencies",
        "text": """The Central Government may exempt government agencies from certain provisions of this Act for:
(a) processing necessary for the performance of any function under any law;
(b) sovereignty and integrity of India;
(c) security of the State;
(d) relations with foreign States;
(e) public order;
(f) maintenance of friendly relations with foreign States.

Such exemptions require a written order with reasons recorded.

Compliance Obligation: Government agencies claiming exemptions must publish the exemption order or reference in their privacy notices.""",
    },
    {
        "id": "DPDP Section 27",
        "title": "Breach Notification to Board and Data Principals",
        "text": """In the event of a personal data breach, the Data Fiduciary must:
(a) notify the Data Protection Board of India in the prescribed form and manner;
(b) notify each affected Data Principal in the prescribed form and manner;
(c) provide details of the breach, likely consequences, measures taken, and steps Data Principals should take.

Compliance Obligation: Privacy policies must describe the breach notification procedure, timelines, and what affected individuals can expect in the event of a data breach.""",
    },
    {
        "id": "DPDP Section 28",
        "title": "Grievance Redressal by Data Fiduciary",
        "text": """Every Data Fiduciary must have an accessible and effective mechanism for grievance redressal. The mechanism must include:
(a) a designated point of contact;
(b) a clear process for registering complaints;
(c) prescribed timelines for response;
(d) escalation to the Data Protection Board if unresolved.

Compliance Obligation: Privacy policies must detail the complete grievance redressal mechanism, including contact information, process steps, timelines, and Board escalation rights.""",
    },
    {
        "id": "DPDP Section 32",
        "title": "Penalties for Non-Compliance",
        "text": """The Data Protection Board of India may impose penalties for:
(a) failure to comply with obligations of Data Fiduciaries — up to Rupees two hundred and fifty crores;
(b) failure to comply with duties of Data Principals — up to Rupees ten thousand;
(c) failure to comply with obligations of Significant Data Fiduciaries — higher penalties;
(d) failure to prevent data breach or report it — up to Rupees two hundred and fifty crores.

Compliance Obligation: Privacy policies should acknowledge the legal consequences of non-compliance and demonstrate good-faith efforts to comply with all DPDP obligations.""",
    },
    {
        "id": "DPDP - Data Minimization Principle",
        "title": "Data Minimization (Implied across Sections 4, 5, 6)",
        "text": """The DPDP Act 2023 embodies the principle of data minimization: Data Fiduciaries must collect only personal data that is necessary for the specified purpose. Collection must be limited to what is adequate, relevant, and not excessive.

Compliance Obligation: Privacy policies must demonstrate data minimization by clearly limiting data collection to what is strictly necessary for stated purposes. Over-collection or blanket data collection is non-compliant.""",
    },
    {
        "id": "DPDP - Transparency Principle",
        "title": "Transparency (Implied across Sections 5, 6, 8)",
        "text": """The DPDP Act 2023 requires transparency in all data processing activities. Data Principals must be informed about who is processing their data, why, for how long, and what their rights are. Information must be provided in a concise, transparent, intelligible, and easily accessible form.

Compliance Obligation: Privacy policies must be written in plain language, be easily accessible, and comprehensively disclose all processing activities. Complex legal jargon or buried disclosures are non-compliant.""",
    },
    {
        "id": "DPDP - Third-Party Sharing",
        "title": "Third-Party Disclosure and Sharing",
        "text": """Under the DPDP Act 2023, sharing personal data with third parties requires:
(a) explicit disclosure in the privacy notice of all categories of recipients;
(b) the Data Principal's consent if not covered by a legal basis under Section 4;
(c) appropriate contractual safeguards when sharing with processors;
(d) accountability for third-party processing.

Compliance Obligation: Privacy policies must list all categories of third parties who receive personal data, the purposes of sharing, and the safeguards in place. Blanket 'trusted partners' language without specifics is non-compliant.""",
    },
]
