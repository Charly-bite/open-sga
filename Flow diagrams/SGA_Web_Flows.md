# SGA Web Application Flow Diagrams

Copy the code blocks below and paste them into [GraphvizOnline](https://dreampuf.github.io/GraphvizOnline/) to generate the flow diagrams.

## 1. Authentication Flow

```dot
digraph AuthFlow {
    rankdir=TB;
    node [shape=box, style=rounded, fontname="Arial"];
    edge [fontname="Arial", fontsize=10];

    Start [shape=ellipse, label="User Accesses App"];
    CheckAuth [shape=diamond, label="Is Authenticated?"];
    Dashboard [label="Main Dashboard\n(/main/dashboard)"];
    LoginPage [label="Login Page\n(/auth/login)"];
    SubmitLogin [label="Submit Credentials\n(POST /auth/login)"];
    ValidateCreds [shape=diamond, label="Valid Credentials?"];
    CheckActive [shape=diamond, label="Is Account Active?"];
    CheckPassword [shape=diamond, label="Must Change Password?"];
    ChangePasswordPage [label="Change Password Page\n(/auth/change-password)"];
    SubmitPassword [label="Submit New Password\n(POST /auth/change-password)"];
    UpdatePassword [label="Update Password in DB"];
    Logout [label="Logout\n(/auth/logout)"];

    Start -> CheckAuth;
    CheckAuth -> Dashboard [label="Yes"];
    CheckAuth -> LoginPage [label="No"];
    
    LoginPage -> SubmitLogin;
    SubmitLogin -> ValidateCreds;
    
    ValidateCreds -> LoginPage [label="No (Show Error)"];
    ValidateCreds -> CheckActive [label="Yes"];
    
    CheckActive -> LoginPage [label="No (Show Error)"];
    CheckActive -> CheckPassword [label="Yes"];
    
    CheckPassword -> ChangePasswordPage [label="Yes"];
    CheckPassword -> Dashboard [label="No"];
    
    ChangePasswordPage -> SubmitPassword;
    SubmitPassword -> UpdatePassword [label="Valid Input"];
    SubmitPassword -> ChangePasswordPage [label="Invalid Input"];
    UpdatePassword -> Dashboard;
    
    Dashboard -> Logout [label="User clicks Logout"];
    Logout -> LoginPage;
}
```

## 2. Label Generation Flow

```dot
digraph LabelGenerationFlow {
    rankdir=TB;
    node [shape=box, style=rounded, fontname="Arial"];
    edge [fontname="Arial", fontsize=10];

    Start [shape=ellipse, label="Labels Page\n(/labels/)"];
    ScanBarcode [label="Scan Barcode / Enter Code"];
    ResolveProduct [shape=diamond, label="Resolve Product\n(SmartLabelManager)"];
    ShowError [label="Show Error Message"];
    GetTareBatch [label="Get Tare & Batch Info\n(from CSV)"];
    AddToQueue [label="Add to Print Queue\n(Session)"];
    UpdateUI [label="Update Queue UI"];
    
    SelectItems [label="Select Items in Queue"];
    ClickPrint [label="Click Print Selected"];
    SelectTemplate [shape=diamond, label="Template Selected?"];
    GeneratePDF [label="Generate PDF\n(GHSLabelGenerator)"];
    GeneratePDFTemplate [label="Generate PDF from Template\n(GHSLabelGenerator)"];
    ReturnPDF [shape=ellipse, label="Return PDF to Browser\n(application/pdf)"];
    
    Start -> ScanBarcode;
    ScanBarcode -> ResolveProduct;
    
    ResolveProduct -> ShowError [label="Not Found"];
    ResolveProduct -> GetTareBatch [label="Found"];
    
    GetTareBatch -> AddToQueue;
    AddToQueue -> UpdateUI;
    
    UpdateUI -> SelectItems;
    SelectItems -> ClickPrint;
    ClickPrint -> SelectTemplate;
    
    SelectTemplate -> GeneratePDFTemplate [label="Yes"];
    SelectTemplate -> GeneratePDF [label="No (Default)"];
    
    GeneratePDF -> ReturnPDF;
    GeneratePDFTemplate -> ReturnPDF;
}
```

## 3. Order Processing Flow (SAP Integration)

```dot
digraph OrderProcessingFlow {
    rankdir=TB;
    node [shape=box, style=rounded, fontname="Arial"];
    edge [fontname="Arial", fontsize=10];

    Start [shape=ellipse, label="Orders Dashboard\n(/orders/)"];
    ViewOrder [label="Click Order Details\n(/orders/<id>)"];
    FetchOrder [label="Fetch Order Data\n(OrderStatusManager)"];
    DisplayOrder [label="Display Order Items"];
    
    SelectOrderItems [label="Select Items to Print"];
    ClickPrintOrder [label="Click Print Labels"];
    SendToQueue [label="Send Items to Label Queue\n(POST /labels/api/queue/add-batch)"];
    RedirectLabels [label="Redirect to Labels Page"];
    
    UpdateStatus [label="Change Order Status\n(POST /orders/<id>/status)"];
    CheckPermission [shape=diamond, label="Has Permission?"];
    SaveStatus [label="Save Status to DB\n(order_status_db.json)"];
    ReturnSuccess [shape=ellipse, label="Return Success JSON"];
    ReturnError [shape=ellipse, label="Return Error JSON"];

    Start -> ViewOrder;
    ViewOrder -> FetchOrder;
    FetchOrder -> DisplayOrder;
    
    DisplayOrder -> SelectOrderItems;
    SelectOrderItems -> ClickPrintOrder;
    ClickPrintOrder -> SendToQueue;
    SendToQueue -> RedirectLabels;
    
    DisplayOrder -> UpdateStatus [label="Operator Action"];
    UpdateStatus -> CheckPermission;
    CheckPermission -> SaveStatus [label="Yes"];
    CheckPermission -> ReturnError [label="No"];
    SaveStatus -> ReturnSuccess;
}
```

## 4. Product Management Flow

```dot
digraph ProductManagementFlow {
    rankdir=TB;
    node [shape=box, style=rounded, fontname="Arial"];
    edge [fontname="Arial", fontsize=10];

    Start [shape=ellipse, label="Products Page\n(/products/)"];
    LoadProducts [label="Load Products from DB\n(SmartLabelManager)"];
    ApplyPagination [label="Apply Pagination & Search"];
    EnrichPictograms [label="Enrich with Pictograms"];
    DisplayTable [label="Display Products Table"];
    
    SearchAPI [label="Search API\n(/products/search?q=...)"];
    QueryDB [label="Query Product DB"];
    ReturnJSON [shape=ellipse, label="Return JSON Results"];
    
    Start -> LoadProducts;
    LoadProducts -> ApplyPagination;
    ApplyPagination -> EnrichPictograms;
    EnrichPictograms -> DisplayTable;
    
    SearchAPI -> QueryDB;
    QueryDB -> ReturnJSON;
}
```

## 5. Template Management Flow

```dot
digraph TemplateManagementFlow {
    rankdir=TB;
    node [shape=box, style=rounded, fontname="Arial"];
    edge [fontname="Arial", fontsize=10];

    Start [shape=ellipse, label="Templates Page\n(/templates/)"];
    ListTemplates [label="List Available Templates\n(TemplateManager)"];
    
    Action [shape=diamond, label="User Action"];
    
    CreateNew [label="Create New\n(/templates/designer)"];
    EditExisting [label="Edit Existing\n(/templates/designer/<id>)"];
    Duplicate [label="Duplicate\n(POST /templates/api/duplicate/<id>)"];
    Delete [label="Delete\n(DELETE /templates/api/<id>)"];
    
    LoadDesigner [label="Load Drag & Drop Designer"];
    ModifyTemplate [label="Modify Template Elements"];
    SaveTemplate [label="Save Template\n(POST /templates/api/save)"];
    CheckAdmin [shape=diamond, label="Is Admin?"];
    WriteJSON [label="Write to JSON File\n(label_templates/)"];
    ReturnResult [shape=ellipse, label="Return Success/Error"];

    Start -> ListTemplates;
    ListTemplates -> Action;
    
    Action -> CreateNew;
    Action -> EditExisting;
    Action -> Duplicate;
    Action -> Delete;
    
    CreateNew -> LoadDesigner;
    EditExisting -> LoadDesigner;
    
    LoadDesigner -> ModifyTemplate;
    ModifyTemplate -> SaveTemplate;
    
    SaveTemplate -> CheckAdmin;
    CheckAdmin -> WriteJSON [label="Yes"];
    CheckAdmin -> ReturnResult [label="No (Error)"];
    WriteJSON -> ReturnResult;
    
    Duplicate -> CheckAdmin;
    Delete -> CheckAdmin;
}
```
