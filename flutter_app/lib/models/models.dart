// ── 数据模型层 ──
// 本文件提供对 lib/models/ 下所有数据模型的统一导出。
// 页面中可直接 `import 'package:flutter_app/models/models.dart';` 导入全部类型。
//
// 已有模型：
//   chat_message.dart   — ChatMessage, ChatMessageType, AgentInfo, AutonomyMode
//   project.dart        — Project, ProjectStatus
//   user.dart           — User, UserRole
//   budget.dart         — Budget, BudgetLine, BudgetStatus
//   task.dart           — Task, TaskStatus
//   material.dart       — Material, MaterialCategory
//   construction.dart   — Construction, ConstructionStatus
//   settlement.dart     — Settlement, SettlementLine, SettlementStatus
//   smart_home.dart     — SmartHome, SmartDevice
//   scene_automation.dart — SceneAutomation, SceneType
//   procurement.dart    — Procurement, ProcurementLine, ProcurementStatus

export 'chat_message.dart';
export 'project.dart';
export 'user.dart';
export 'budget.dart';
export 'task.dart';
export 'material.dart';
export 'construction.dart';
export 'settlement.dart';
export 'smart_home.dart';
export 'scene_automation.dart';
export 'procurement.dart';
