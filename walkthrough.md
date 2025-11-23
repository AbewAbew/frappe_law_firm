# IP Management App Walkthrough

## Overview
A new Frappe app `ip_management` has been created to handle Intellectual Property cases. This app includes a workflow engine that automates task creation based on case status changes.

## Features Implemented

### 1. New App: `ip_management`
-   **Installed on Site**: `lawfirm.localhost`
-   **Module**: `IP Management`

### 2. DocTypes
The following DocTypes have been created and migrated:

| DocType | Type | Description |
| :--- | :--- | :--- |
| **IP Request Type** | Master | Categorizes cases (e.g., "Trademark", "Patent"). Links to Billing Item. |
| **IP Case Status** | Master | Tracks progress (e.g., "Filed", "Examination"). Includes color coding. |
| **IP Case** | Document | Central document for managing IP cases. Links to Applicant (Customer), Request Type, and Status. Key field: `IP Case ID`. |
| **IP Workflow Rule** | Document | Defines automation rules. Triggers tasks based on status changes. |
| **IP Task** | Document | Tasks generated automatically by the workflow engine. |
| **IP Case History** | Child Table | Logs all status changes in an IP Case. |

### 3. Automation Logic
-   **Trigger**: When `IP Case` status changes.
-   **Action**:
    1.  Logs the change in `Status History`.
    2.  Searches for an active `IP Workflow Rule` matching the new status.
    3.  Calculates the `Due Date` (Today + Days defined in Rule).
    4.  Creates a new `IP Task` assigned to the current user.

## How to Test

### Step 1: Setup Masters
1.  Go to **IP Request Type List** and create a type (e.g., "Trademark").
2.  Go to **IP Case Status List** and create a status (e.g., "Filed").

### Step 2: Define a Rule
1.  Go to **IP Workflow Rule List**.
2.  Create a new rule:
    -   **Triggering Status**: "Filed"
    -   **Days to Deadline**: 14
    -   **Task Template**: "Check filing receipt for {{ trademark_name }}"
    -   **Is Active**: Checked

### Step 3: Create a Case
1.  Go to **IP Case List**.
2.  Create a new case:
    -   **MLA ID**: "TM-2025-001"
    -   **Trademark Name**: "My Brand"
    -   **Status**: (Leave empty or set to something else initially)
3.  Save.

### Step 4: Trigger Workflow
1.  Open the **IP Case** you just created.
2.  Change **Case Status** to "Filed".
3.  Save.

### Verification
-   Check the **Status History** table in the IP Case. It should show the update.
-   Go to **IP Task List**. You should see a new task:
    -   **Subject**: "Check filing receipt for My Brand"
    -   **Due Date**: 14 days from today.

## User Guide: Getting Started

Here is a step-by-step guide to setting up your IP Management system from scratch.

### 1. Create "Masters" (The Basics)
Before you can create cases, you need to define the types of requests and statuses you use.

**A. Create Request Types**
1.  Search for **IP Request Type List**.
2.  Click **Add IP Request Type**.
3.  Enter a name (e.g., "Trademark Application", "Patent Filing", "Copyright Registration").
4.  Save.
5.  Repeat for all the services you offer.

**B. Create Case Statuses**
1.  Search for **IP Case Status List**.
2.  Click **Add IP Case Status**.
3.  Enter a status name (e.g., "New", "Filed", "Examination", "Publication", "Registered", "Refused").
4.  Pick a **Color** for each status (e.g., Blue for New, Yellow for Filed, Green for Registered).
5.  Save.

### 2. Setup Automation Rules (The Magic)
This is where you tell the system what to do automatically.

**Example: "When a case is Filed, remind me to check the receipt in 2 weeks."**

1.  Search for **IP Workflow Rule List**.
2.  Click **Add IP Workflow Rule**.
3.  **Triggering Status**: Select "Filed".
4.  **Days to Deadline**: Enter `14`.
5.  **Task Template**: Enter `Check filing receipt for {{ trademark_name }}`.
    *   *Note: `{{ trademark_name }}` will be replaced by the actual name of the trademark in the case.*
6.  **Is Active**: Ensure this is checked.
7.  Save.

### 3. Manage a Case (Day-to-Day)
Now you are ready to work!

1.  Go to **IP Case List**.
2.  Click **Add IP Case**.
3.  **MLA ID**: Enter your internal file number (e.g., "TM-001").
4.  **Trademark Name**: Enter the brand name.
5.  **Request Type**: Select "Trademark Application".
6.  **Case Status**: Select "New".
7.  Save.

**Triggering the Rule:**
1.  When you have filed the application, open the **IP Case**.
2.  Change **Case Status** to "Filed".
3.  Save.
4.  Look at the **Status History** table at the bottom; it will record this change.
5.  Go to **IP Task List** (or check the "Connections" button at the top). You will see a new task created automatically!

### 4. User & Permissions Setup
Since this is a fresh app, you need to define who can access it.

**A. Configure Permissions (One-Time Setup)**
You need to link your new Roles to your new DocTypes.

1.  Search for **Role Permissions Manager**.
2.  **Select Document Type**: `IP Case`.
3.  **Select Role**: `IP Manager`.
4.  Click **Add a New Rule**.
5.  **Check Permissions**: Read, Write, Create, Delete, Submit, Cancel, Amend, Report, Import, Export.
6.  Click **Add**.
7.  *Repeat for `IP Staff` role (maybe give them only Read, Write, Create).*
8.  **Repeat these steps** for other DocTypes:
    *   `IP Task`
    *   `IP Workflow Rule` (Managers only)
    *   `IP Request Type` (Managers only)
    *   `IP Case Status` (Managers only)

**B. Create a User**
1.  Search for **User List**.
2.  Click **Add User**.
3.  Enter **Email** and **First Name**.
4.  **Roles**: Scroll down and check `IP Manager` or `IP Staff`.
5.  Save.

## 4. Designing Reports (Print Designer)
We have installed **Print Designer** to create beautiful documents.
1.  Go to **Print Designer** in the Desk.
2.  Create a new **Print Format**.
3.  Select DocType: **IP Case**.
4.  Use the drag-and-drop editor to design your report (add Logo, Case ID, Status, etc.).
5.  Save and use this format when printing a case.
