# 电控制造不良品分析 — 字段字典（Task 1 产出，待业务签字）

> 适用范围：MES / ERP / WMS 三源打通的不良品分析场景。
> 状态：设计稿（占位字段需由质量与 IT 在 Task 1 对齐后填实）。
> 上游方案：[电控不良品分析方案](../../C:/Users/GOBAO/AppData/Roaming/Qoder/SharedClientCache/cache/plans/)（已签字）。

## 1. 口径与原则

1. 只读 SELECT；SQL 时间跨度建议 ≤ 90 天，超出需分段聚合。
2. 所有字段必须标注源系统 / 表名 / 业务含义 / 数据类型 / 是否可空 / 样例值。
3. 统一**跨源主键**：`WorkOrderNo`（工单号）、`MaterialCode`（物料编码）、`BatchNo`（批次号）、`SupplierCode`（供应商编码）。
4. 不良代码字典以 MES 为准，ERP/WMS 来源通过映射表归一到标准码。
5. 时间字段统一为 `datetime2`，字段命名后缀 `_AT`；所有报表按工厂本地时区。

## 2. MES 业务字段（源：MES SQL Server，占位）

### 2.1 `dbo.MfgWorkOrder`（工单）

| 字段 | 类型 | 可空 | 含义 | 跨源键 | 备注 |
|---|---|---|---|---|---|
| WorkOrderId | bigint | N | 工单主键 | - | PK |
| WorkOrderNo | nvarchar(64) | N | 工单号 | Cross-Key | 与 ERP 同名 |
| MaterialCode | nvarchar(64) | N | 成品物料编码 | Cross-Key | 与 ERP / WMS 对齐 |
| ProductionLine | nvarchar(32) | Y | 产线编码 | - | 例：LINE-A01 |
| PlannedQty | decimal(18,2) | N | 计划数量 | - | |
| OutputQty | decimal(18,2) | N | 产出数量 | - | |
| DefectQty | decimal(18,2) | N | 不良数量 | - | |
| Status | nvarchar(16) | N | 状态 | - | PLAN/RUN/CLOSED |
| StartAt | datetime2 | Y | 开工时间 | - | |
| CloseAt | datetime2 | Y | 关单时间 | - | |

### 2.2 `dbo.MfgDefectRecord`（不良记录）

| 字段 | 类型 | 可空 | 含义 | 跨源键 | 备注 |
|---|---|---|---|---|---|
| DefectId | bigint | N | 不良记录主键 | - | PK |
| WorkOrderNo | nvarchar(64) | N | 工单号 | Cross-Key | |
| BatchNo | nvarchar(64) | Y | 生产批次号 | Cross-Key | 与 WMS 对齐 |
| StationCode | nvarchar(32) | N | 工位编码 | - | FK → MfgStation |
| DefectCode | nvarchar(32) | N | 不良代码 | - | 见第 5 节字典 |
| DefectQty | decimal(18,2) | N | 不良数量 | - | |
| DispositionType | nvarchar(16) | N | 处置类型 | - | REWORK/SCRAP/USE |
| InspectAt | datetime2 | N | 检验时间 | - | |
| InspectorCode | nvarchar(32) | Y | 检验员 | - | |

### 2.3 `dbo.MfgInspectionItem`（检验项）

| 字段 | 类型 | 可空 | 含义 | 备注 |
|---|---|---|---|---|
| ItemId | bigint | N | 主键 | PK |
| WorkOrderNo | nvarchar(64) | N | 工单号 | |
| ItemCode | nvarchar(32) | N | 检验项编码 | |
| ItemName | nvarchar(128) | N | 检验项名称 | |
| Spec | nvarchar(256) | Y | 规格/限值 | |
| Result | nvarchar(16) | N | 结果 | PASS/FAIL |

### 2.4 `dbo.MfgStation`（工位）

| 字段 | 类型 | 可空 | 含义 | 备注 |
|---|---|---|---|---|
| StationCode | nvarchar(32) | N | 工位编码 | PK |
| StationName | nvarchar(64) | N | 工位名称 | |
| ProductionLine | nvarchar(32) | N | 所属产线 | |
| ProcessType | nvarchar(32) | Y | 工序类型 | 焊接/贴装/老化/测试 |

## 3. WMS 业务字段（源：WMS SQL Server，占位）

### 3.1 `dbo.IqcInspection`（来料检验）

| 字段 | 类型 | 可空 | 含义 | 跨源键 | 备注 |
|---|---|---|---|---|---|
| IqcId | bigint | N | 主键 | - | PK |
| BatchNo | nvarchar(64) | N | 来料批次 | Cross-Key | |
| MaterialCode | nvarchar(64) | N | 物料编码 | Cross-Key | |
| SupplierCode | nvarchar(64) | N | 供应商编码 | Cross-Key | |
| PoNo | nvarchar(64) | Y | 采购订单号 | - | 与 ERP 对齐 |
| InspectQty | decimal(18,2) | N | 检验数量 | - | |
| DefectQty | decimal(18,2) | N | 不良数量 | - | |
| Result | nvarchar(16) | N | 结果 | - | PASS/FAIL |
| InspectAt | datetime2 | N | 检验时间 | - | |

### 3.2 `dbo.InventoryBatch`（库存批次）

| 字段 | 类型 | 可空 | 含义 | 跨源键 | 备注 |
|---|---|---|---|---|---|
| BatchNo | nvarchar(64) | N | 批次号 | Cross-Key | PK |
| MaterialCode | nvarchar(64) | N | 物料编码 | Cross-Key | |
| SupplierCode | nvarchar(64) | Y | 供应商编码 | Cross-Key | |
| WarehouseCode | nvarchar(32) | N | 仓库 | - | |
| InQty | decimal(18,2) | N | 入库数量 | - | |
| OutQty | decimal(18,2) | N | 出库数量 | - | |
| CreatedAt | datetime2 | N | 入库时间 | - | |

## 4. ERP 业务字段（源：ERP REST API，占位）

> 通过新建 `erp-api-mcp` MCP Server 以工具函数形式暴露，字段命名与 API 返回 JSON 保持一致（camelCase → 文档中展开为中文语义）。

### 4.1 `GET /materials`（物料主数据）

| JSON 字段 | 类型 | 含义 | 跨源键 |
|---|---|---|---|
| materialCode | string | 物料编码 | Cross-Key |
| materialName | string | 物料名称 | - |
| category | string | 物料类别 | - |
| unit | string | 单位 | - |
| status | string | 状态 A/I | - |

### 4.2 `GET /suppliers`（供应商）

| JSON 字段 | 类型 | 含义 | 跨源键 |
|---|---|---|---|
| supplierCode | string | 供应商编码 | Cross-Key |
| supplierName | string | 供应商名称 | - |
| grade | string | 供应商等级 A/B/C | - |

### 4.3 `GET /purchase-batches`（采购批次/来料）

| JSON 字段 | 类型 | 含义 | 跨源键 |
|---|---|---|---|
| poNo | string | 采购订单号 | 与 WMS 对齐 |
| batchNo | string | 批次号 | Cross-Key |
| materialCode | string | 物料编码 | Cross-Key |
| supplierCode | string | 供应商编码 | Cross-Key |
| qty | number | 采购数量 | - |
| receivedAt | string(datetime) | 到货时间 | - |

### 4.4 `GET /bom/{productCode}`（BOM 展开）

| JSON 字段 | 类型 | 含义 |
|---|---|---|
| parentCode | string | 父件物料编码 |
| childCode | string | 子件物料编码 |
| qty | number | 单位用量 |
| level | int | 层级 |

## 5. 不良代码字典（占位，需业务提供最终清单）

| 标准码 | 名称 | 典型工位 | MES 原始码映射 | 备注 |
|---|---|---|---|---|
| DEF-SOLDER-01 | 虚焊 | 焊接/回流 | S01, SLDR-EMPTY | |
| DEF-SOLDER-02 | 连锡 | 焊接/回流 | S02, SLDR-BRIDGE | |
| DEF-SMT-01 | 贴偏 | SMT | M01 | |
| DEF-SMT-02 | 立碑 | SMT | M02 | |
| DEF-FUNC-01 | 功能测试不过 | FCT | F01, FUNC-NG | |
| DEF-AGING-01 | 老化失效 | 老化 | A01 | |
| DEF-APPEARANCE-01 | 外观划伤 | 外观 | V01 | |
| DEF-PACK-01 | 包装破损 | 包装 | P01 | |

> 不良代码映射表后续在 Skill 内作为只读常量维护；新增不良代码需经 QA 主管评审。

## 6. 验证清单（签字前必过）

- [ ] 每张表的 PK / 跨源键已与 IT 确认。
- [ ] 跨源键样例值（1 条完整链路：ERP 采购批次 → WMS 入库批次 → MES 工单不良）可追溯。
- [ ] 不良代码字典覆盖率 ≥ 90%（历史 1 年不良记录抽样）。
- [ ] 时间字段时区统一。
- [ ] ERP API 鉴权方式与限流阈值明确。

## 7. 变更记录

| 日期 | 版本 | 修改人 | 说明 |
|---|---|---|---|
| TBD | v0.1 | TBD | 初始设计稿 |
