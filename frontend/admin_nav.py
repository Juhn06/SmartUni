"""Admin system navigation — 4 function groups."""

ADMIN_SYS_GROUPS = [
    {
        "id": "accounts",
        "title": "Tài khoản & phân quyền",
        "title_en": "Accounts & access",
        "desc": "Người dùng, bộ phận, vai trò và phạm vi dữ liệu",
        "desc_en": "Users, departments, roles and data scopes",
        "items": [
            {
                "route": "admin_users",
                "label": "Người dùng",
                "label_en": "Users",
                "hint": "Khóa / admin / reset MK",
            },
            {
                "route": "admin_departments",
                "label": "Bộ phận",
                "label_en": "Departments",
                "hint": "Danh sách & thành viên",
            },
            {
                "route": "admin_permissions",
                "label": "Phân quyền",
                "label_en": "Permissions",
                "hint": "Chức năng + scope CT",
            },
        ],
    },
    {
        "id": "requests",
        "title": "Theo dõi yêu cầu",
        "title_en": "Request tracking",
        "desc": "Đề xuất góp ý theo chức năng — lọc, xử lý, xuất Excel",
        "desc_en": "Feature suggestions — filter, process, export",
        "items": [
            {
                "route": "admin_suggestions",
                "label": "Đề xuất / góp ý",
                "label_en": "Suggestions",
                "hint": "Trạng thái & xuất file",
            },
        ],
    },
    {
        "id": "catalogs",
        "title": "Danh mục trạng thái",
        "title_en": "Status catalogs",
        "desc": "Giá trị dropdown dùng chung toàn hệ thống",
        "desc_en": "Shared dropdown values across the system",
        "items": [
            {
                "route": "admin_status_catalog",
                "label": "Danh mục trạng thái",
                "label_en": "Status types",
                "hint": "Hồ sơ, phí, nghỉ phép…",
            },
            {
                "route": "admin_book_categories",
                "label": "Danh mục sách",
                "label_en": "Book categories",
                "hint": "Thư viện / sách",
            },
            {
                "route": "admin_settings",
                "label": "Cấu hình hệ thống",
                "label_en": "System settings",
                "hint": "Development / Production",
            },
        ],
    },
    {
        "id": "reports",
        "title": "Thống kê báo cáo",
        "title_en": "Reports",
        "desc": "Tổng hợp số liệu vận hành và nội dung",
        "desc_en": "Operational and content metrics",
        "items": [
            {
                "route": "admin_system_hub",
                "label": "Tổng quan Admin",
                "label_en": "Admin overview",
                "hint": "Hub 4 nhóm",
            },
            {
                "route": "ops_reports",
                "label": "Báo cáo Ops",
                "label_en": "Ops reports",
                "hint": "Pipeline theo CT",
            },
            {
                "route": "admin_index",
                "label": "Nội dung (Articles)",
                "label_en": "Content dashboard",
                "hint": "Articles / books",
            },
        ],
    },
]
