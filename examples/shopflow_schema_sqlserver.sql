CREATE TABLE [dbo].[Tenants] (
  [Id] INT IDENTITY(1,1) PRIMARY KEY,
  [Name] NVARCHAR(120) NOT NULL,
  [Posture] NVARCHAR(20) NOT NULL
);

CREATE TABLE [dbo].[Orders] (
  [Id] INT IDENTITY(1,1) PRIMARY KEY,
  [TenantId] INT NOT NULL,
  [Status] NVARCHAR(20) NOT NULL,
  [Total] DECIMAL(10,2) NOT NULL,
  CONSTRAINT [FK_Orders_Tenants] FOREIGN KEY ([TenantId]) REFERENCES [dbo].[Tenants]([Id]),
  CONSTRAINT [CK_Orders_Status] CHECK ([Status] IN ('draft','pending','confirmed','cancelled'))
);
