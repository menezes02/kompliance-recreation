# Kompliance Web App — Read-Only Functional Map

Audit date: 2026-07-18  
Target: `https://kompliance.lgsafety.ie/`  
Access level observed: customer/company administrator

## Safety boundary used during discovery

- Navigation and screen viewing only.
- No records were created, edited, approved, assigned, deleted, or submitted.
- No files were uploaded or downloaded.
- No QR codes were downloaded.
- No emails, invitations, contact messages, or password changes were sent.
- No filters or form fields were changed.
- Create and edit pages were opened only to identify their schemas.
- Public induction registration was viewed only up to the registration form.

## Local platform extensions

These routes belong to the recreated platform and were not used to mutate the
source application:

| Route | Purpose |
|---|---|
| `/worker/` | Worker registration, login, recovery and worker-owned passport |
| `/worker/public/:token` | Minimal worker-controlled QR profile |
| `/worker/share/:token` | Revocable company-specific consent link |
| `/shared-workers` | QR/manual company access requests, consent history, document review and workforce import |
| `/workflow-centre` | Routed requests, conversations, induction approvals, notifications and department contacts |
| `/worker/#inbox` | Worker access approval/decline, request creation, conversation replies, induction status and notifications |
| `/system` | System/privacy controls, notification delivery history and authorised tenant migration history |
| `/api/v1/shared-workers` | Bearer-token REST list for active consent grants |
| `/api/v1/workers/:id/*` | Scoped profile, certification, training, induction and document resources |
| `/api/openapi.json` | OpenAPI 3.1 contract for consent and integration routes |

All local tenant records are isolated by `company_id`. The authorised source
snapshot belongs only to the original customer tenant and remains immutable.

## Application shell

The authenticated application uses a single top navigation bar with:

- Workers
  - Roles
  - Sites
  - Workers
- Subcontractors
- Forms
  - Forms
  - Form Distributions
- Trainings
  - Training Questions
- Assets
- HSA Forms
  - GA1 Forms
  - GA2 Forms
  - GA3 Forms
  - GA3 Scaffold Inspections
  - AF3 Forms
  - Handover Certificate
  - GA2 Manual Forms
  - GA3 Manual Forms
  - Risk Assessment / Safety Statement
- Shared Documents
- Contact
- Company menu
  - My profile
  - Change Password
  - Logout

Inductions are available from the dashboard but are not present as a primary navigation item.

## Route inventory

### Authentication and account

| Route | Purpose | Verified controls |
|---|---|---|
| `/login` | Company login | Email, password, remember me, forgot password, sign in |
| `/password/reset` | Password reset entry | Linked from login; not submitted |
| `/company-profile` | Company/admin profile | Company name, company email, admin name, disabled admin email, phone, address, logo, Update |
| `/change-password` | Password change | Current password, new password, confirm password, Update password |
| `/logout` | End session | Present in account menu; never activated |

### Dashboard

| Route | Purpose |
|---|---|
| `/` | KPI dashboard and entry point to all major datasets |

Dashboard tiles show live counts for:

- Total sites
- Total workers, with an unapproved-worker badge
- Subcontractors
- Custom forms
- GA2
- GA3
- GA3 Scaffold Inspections
- AF3
- Handover Certificates
- GA2 Manual
- GA3 Manual
- GA1
- Risk Assessments / Safety Statements
- Inductions

Submitted-form tiles can show unread-count badges.

### Sites and roles

| Route pattern | Purpose |
|---|---|
| `/sites` | Searchable/paginated site list |
| `/sites/create` | Add a site |
| `/sites/:id/edit` | Edit a site |
| `/workers-roles` | Searchable/paginated role list |
| `/workers-roles/create` | Add one or more roles |
| `/workers-roles/:id/edit` | Edit a role |

Site fields:

- Site name
- Address
- Additional remarks

Site table:

- Number
- Name
- Address
- Created at
- Actions: edit and delete

Role fields:

- Role name
- Add another role row

Role table:

- Number
- Name
- Created at
- Updated at
- Actions: edit and delete

### Workers

| Route pattern | Purpose |
|---|---|
| `/workers` | Worker list, filtering, approval/training overview |
| `/workers/create` | Add permanent or temporary worker |
| `/workers/:id/edit` | Edit worker |
| `/workers/safepass/show/:id` | Read-only Safe Pass and training details |
| `/workers/:id/inductions` | Worker induction status by site |
| `/workers/:workerId/inductions/:siteId/certificate/download` | Completed induction certificate |

Worker-list filters:

- Sites
- Roles
- Worker type: Permanent or Temporary
- Subcontractor
- Status: Approved or Pending
- Global text search
- Page size: 10, 25, 50, or 100

Worker-list columns:

- Number
- Worker ID
- Name
- Email
- Subcontractor
- Assigned sites
- Assigned roles
- Training status
- Safe Pass expiry date
- Induction status
- Sites inducted
- Phone number
- Actions

Worker row actions:

- Safe Pass Details
- View Inductions
- Edit
- Delete

Permanent worker details:

- Name
- Email
- Optional worker ID
- Phone country code and phone number
- Emergency country code and emergency phone number
- Emergency contact name
- Emergency contact address
- Multiple sites
- Multiple roles
- Subcontractor or No Subcontractor
- Worker photo
- Relevant medical history

Temporary worker mode also exposes validity dates.

Training-record behavior:

- Each configured training question has Yes/No.
- A positive answer has an expiry-date field and image evidence input in the DOM.
- The current customer configuration includes Manual Handling, several CSCS/QSCS categories, plant operation, scaffolding, lifting, road works, roofing, MEWP, forklift, induction, and related qualifications.
- The details screen displays answer, expiry, active/remaining-time status, and evidence.

Safe Pass behavior:

- Yes/No
- Safe Pass name
- Safe Pass title/number
- Valid from
- Expiry date
- Image evidence

Worker induction screen:

- Worker identity and active state
- One row per assigned site
- Induction title
- Pending or Completed state
- Completion timestamp
- Certificate download for completed inductions

### Subcontractors

| Route pattern | Purpose |
|---|---|
| `/subcontractor` | Searchable/paginated subcontractor list |
| `/subcontractor/create` | Invite/add subcontractor |
| `/subcontractor/:id/edit` | Edit subcontractor |

Create fields:

- Subcontractor email
- Expiry date

List columns:

- Number
- Subcontractor company name
- Contact name
- Email
- Photo
- Phone number
- Actions: edit and delete

The minimal create form suggests submission may invite or connect an existing subcontractor account. This side effect was not tested.

### Training Questions

| Route pattern | Purpose |
|---|---|
| `/training` | Searchable/paginated training-question list |
| `/training/create` | Add one or more questions |
| `/training/:id/edit` | Edit a question |

Create fields:

- Question text
- Add another question
- Cancel
- Submit

### Custom Forms

| Route pattern | Purpose |
|---|---|
| `/forms` | Form definitions |
| `/forms/create` | Section/question form builder |
| `/forms/:id/edit` | Edit form |
| `/forms/assign/:id` | Assign form to sites and roles |
| `/form/distribution` | Track worker form assignments/submissions |

Form-definition table:

- Number
- Name
- Assigned sites
- Assigned roles
- Created at
- Updated at
- QR code
- Assign form
- Actions

Form row actions:

- QR image
- QR preview/action
- Assign/share
- Show distributions
- Edit
- Delete

Form builder:

- Form name
- Repeating sections
- Section name
- Repeating questions
- Question text
- Question type
- Add question
- Add section

Verified question types:

- Default
- Textbox
- Date Time
- Date
- Time
- Location
- Sign

Assignment screen:

- Multiple sites
- Multiple roles
- Cancel
- Submit
- Existing assignments appear preselected

Distribution screen filters:

- Sites
- Forms
- Status: Pending, Submitted, or Completed
- Search
- Page size

Distribution columns:

- Bulk-select checkbox
- Worker name
- Assigned sites
- Assigned form
- Assigned date
- Submitted date
- Score percentage
- Status
- Actions

A bulk Delete control is present. It was not activated.

### Assets

| Route pattern | Purpose |
|---|---|
| `/appliances` | Asset list |
| `/appliances/create` | Add one or more assets |
| `/appliances/:id/edit` | Edit asset |

Create fields:

- Appliance/asset ID
- Appliance/asset name
- Add another appliance
- Cancel
- Submit

List columns:

- Number
- Subcontractor name
- Asset name
- Asset ID
- Created at
- Updated at
- QR code
- Actions: edit and delete

### Shared Documents

| Route pattern | Purpose |
|---|---|
| `/document` | Shared-document list |
| `/document/create` | Upload a shared document |
| `/document/:id/edit` | Edit document metadata/file |

Create fields:

- Title
- File

Accepted formats shown:

- PDF
- CSV
- Excel
- Word
- PNG
- JPG/JPEG

Maximum size shown: 10 MB.

List columns:

- Number
- Subcontractor name
- Title
- Document
- Type
- Created at
- Updated at
- Actions: open/download, edit, delete

Observed quirk: the create screen's Cancel link targets `/admin/document`, although the customer list route is `/document`.

### HSA/submitted forms

| Route | Purpose |
|---|---|
| `/ga2/form` | GA2 submissions |
| `/ga3/form` | GA3 submissions |
| `/ga3scaffold/form` | GA3 Scaffold Inspections |
| `/af3/form` | AF3 submissions |
| `/handover/form` | Handover Certificates |
| `/ga2_manual/form` | GA2 Manual submissions |
| `/ga3_manual/form` | GA3 Manual submissions |

These seven list screens share the same verified structure:

- Site filter
- Global search
- Page-size selection
- Pagination
- Number
- Subcontractor name
- Site name
- Worker name
- Worker email
- Submitted date
- PDF Download
- Delete

No PDF was opened or downloaded.

### GA1 documents

| Route pattern | Purpose |
|---|---|
| `/ga1` | GA1 document-set list |
| `/ga1/create` | Upload GA1 document set |
| `/ga1/:id` | View documents within a set |
| `/ga1/:id/edit` | Edit set |
| `/ga1/download/:documentId` | Download individual document |

GA1 list:

- Title
- Company
- Optional subcontractor
- Site
- Expiry date
- Expiry status
- View
- Edit
- Delete

Create fields:

- Title
- Optional company subcontractor
- Company site
- Expiry date
- Multiple documents

Accepted formats shown:

- PNG
- WEBP
- JPG/JPEG
- PDF
- DOC/DOCX

Maximum size shown: 10 MB.

The detail page is a searchable one-or-more-document table with individual download actions.

### Risk Assessment / Safety Statement

| Route pattern | Purpose |
|---|---|
| `/risk_assessment` | Document-set list |
| `/risk_assessment/create` | Upload document set |
| `/risk_assessment/:id` | View documents in set |
| `/risk_assessment/:id/edit` | Edit set |
| `/risk_assessment/download/:documentId` | Download document |

The list, create, view, expiry tracking, and document behavior match GA1.

### Inductions

| Route pattern | Purpose |
|---|---|
| `/inductions` | Company induction administration |
| `/inductions/create` | Create induction for an available site |
| `/inductions/:uuid/edit` | Edit site induction |
| `/induction/c/:companyToken` | Public worker entry/resume screen |
| `/induction/c/:companyToken/register` | Public worker registration |

Administration screen:

- Company-wide induction link
- Copy link
- QR code preview/download
- Create induction
- Searchable/paginated list
- Title
- Site
- Submission count
- Status
- Created date
- Edit
- Delete

Verified constraint:

- Only one induction form can exist per site.
- When all sites already have forms, `/inductions/create` returns to the list with an explanatory message.

Induction editor:

- Induction title
- Site
- Repeating subcontractor names
- Add/remove subcontractors
- Repeating pages
- Add/remove pages
- Per-page Text / Media blocks
- Per-page questions
- Question modes: Single Choice or Multiple Choice
- Repeating answer options
- Update Induction Form

The inspected example had 16 pages. No content was changed.

Public worker entry:

- Company identity
- Email lookup/resume
- Continue
- New worker registration link

Public worker registration:

- Worker identity and contact details
- Emergency contact details
- Sites
- Roles
- Subcontractor
- Photo
- Relevant medical history
- Training questions with evidence/expiry fields
- Safe Pass details and evidence
- Confirmation that company Safety Statement and RAMS were read
- Register & Continue

The registration form was not filled or submitted, so the post-registration induction-page flow remains unverified.

### Contact

| Route | Purpose |
|---|---|
| `/contact-us` | Support/contact form |

Fields:

- Name
- Disabled signed-in email
- Subject
- Message
- Submit Now

The screen also displays LG Safety email and telephone contact information. No message was sent.

## Shared list behavior

Most administrative lists use the same interaction model:

- Server/client-side processing overlay
- Page sizes: 10, 25, 50, 100
- Global search
- Pagination
- Alternating table rows
- Action icons with tooltips
- White content card over the application background
- Delete actions use JavaScript controls rather than direct delete URLs

Delete dialogs and server-side deletion behavior were deliberately not tested.

## Visual design system

Verified computed values:

- Font: Poppins, sans-serif
- Body base font: 14 px / weight 400
- Body text: `rgb(84, 84, 84)` / `#545454`
- Navbar: `rgb(7, 54, 92)` / `#07365c`
- Primary action: `rgb(13, 172, 114)` / `#0dac72`
- Content cards: white, 5 px radius, very light shadow
- Page headings: white, 19 px, weight 500
- Table headings: 14 px, weight 500
- Page background image: `/assets/images/background_image.svg`
- Logo: `/assets/images/logo.svg`

Dashboard card palette:

- Sites: `rgb(15, 82, 186)` / `#0f52ba`
- Workers: `rgb(112, 128, 144)` / `#708090`
- Subcontractors: `rgb(218, 165, 32)` / `#daa520`
- Forms: `rgb(123, 154, 94)` / `#7b9a5e`
- Compliance/form tiles: `rgb(122, 63, 157)` / `#7a3f9d`
- Unread/unapproved badges: bright red

Frontend assets observed:

- Poppins from Google Fonts
- Bootstrap CSS
- App/theme CSS
- Custom CSS
- Vendor JS
- App/theme JS
- Custom JS
- Toastr notifications
- SVG dashboard icons

The markup and asset names strongly suggest a Bootstrap/jQuery-style server-rendered application with DataTables and Laravel-style routes/CSRF tokens. This is an implementation inference, not a verified backend stack.

## Inferred domain model

- Company
- Company administrator
- Site
- Worker role
- Worker
- Temporary worker validity
- Subcontractor
- Worker-site assignment
- Worker-role assignment
- Training question
- Worker training record
- Safe Pass
- Custom form
- Form section
- Form question
- Form assignment
- Form distribution/submission
- Asset/appliance
- Shared document
- HSA submission
- GA1 document set
- Risk Assessment document set
- Induction
- Induction subcontractor
- Induction page
- Text/media block
- Choice question and options
- Induction submission
- Induction certificate

## Known UI/content quirks to preserve or intentionally fix

- "Contry Code" typo appears in the authenticated worker form.
- Assets are called "Appliances" in route and create-screen copy.
- GA1 and Risk Assessment view and edit icons can both expose the tooltip "Edit".
- Shared Document create Cancel appears to target `/admin/document`.
- Inductions are on the dashboard but not the main navigation.
- A global loading overlay can remain visible for roughly one to two seconds after navigation.
- Existing form assignments are preselected on the assignment screen.

## Remaining gaps

These require additional authorized roles, safe test data, or explicit permission to submit:

- Worker approval/rejection behavior
- Exact validation messages and field requirements
- Email/invitation flows
- Subcontractor-side portal and permissions
- Form completion experience reached from a QR code
- Scoring rules for custom forms
- PDF layouts and exact HSA form content
- Delete confirmation dialogs and dependencies
- Notifications/toasts after create, update, delete, or assignment
- Public induction resume behavior for an existing worker email
- Post-registration induction page flow
- Induction certificate design
- Media upload/editor behavior in induction pages
- Role-based access differences
- Mobile and tablet layouts
- Password-reset email flow
- Contact-form delivery behavior

## Recommended recreation sequence

1. Recreate the application shell, authentication, route guards, navbar, background, typography, cards, tables, and notifications.
2. Implement Company, Sites, Roles, Workers, Subcontractors, and shared assignments.
3. Implement training questions, worker training records, Safe Pass, approval, and expiry status.
4. Implement the custom form builder, assignments, QR entry, submissions, scoring, and distributions.
5. Implement Assets and Shared Documents.
6. Implement GA1/Risk document sets and HSA submission repositories/PDF exports.
7. Implement induction builder, company token/QR entry, registration, page completion, submissions, and certificates.
8. Add audit logging, role permissions, validation, uploads, email delivery, and background jobs.
9. Verify responsive behavior and parity against every mapped screen.
