IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='product_batches' and xtype='U')
CREATE TABLE product_batches (
    id INT IDENTITY(1,1) PRIMARY KEY,
    product_id VARCHAR(50),
    lote VARCHAR(255),
    fecha_elaboracion DATE,
    fecha_reinspeccion DATE
);
GO
