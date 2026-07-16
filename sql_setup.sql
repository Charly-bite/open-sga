CREATE DATABASE SGA_Database;
GO
USE SGA_Database;
GO
CREATE LOGIN sga_app_user WITH PASSWORD = 'QuimicaBoss_2026!';
GO
CREATE USER sga_app_user FOR LOGIN sga_app_user;
GO
ALTER ROLE db_owner ADD MEMBER sga_app_user;
GO
