import Flutter
import UIKit
import ARKit
import RoomPlan

/// AR 空间测量原生插件 — RoomPlan (iOS 16+)
class ARScanPlugin: NSObject {

    static let channelName = "com.ihome.life/ar_scan"

    private var channel: FlutterMethodChannel?
    private var scanResult: FlutterResult?
    private var tempUsdzPath: String?

    // RoomPlan 对象通过 Any? 存储以避免编译时类型检查
    private var _captureSession: Any?
    private var _captureBuilder: Any?

    // MARK: - Registration

    static func register(with registrar: FlutterPluginRegistrar) {
        let instance = ARScanPlugin()
        let channel = FlutterMethodChannel(
            name: channelName,
            binaryMessenger: registrar.messenger()
        )
        instance.channel = channel
        channel.setMethodCallHandler { call, result in
            instance.handle(call, result: result)
        }
    }

    // MARK: - MethodCall Handler

    func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        switch call.method {
        case "getPlatform":
            result("ios")

        case "getDeviceModel":
            result(getDeviceModel())

        case "detectCapability":
            result(detectCapability())

        case "detectLidar":
            result(detectLidar())

        case "startScan":
            if #available(iOS 16.0, *) {
                startRoomPlanScan(result: result)
            } else {
                result(FlutterError(code: "UNSUPPORTED", message: "需要 iOS 16.0+", details: nil))
            }

        case "cancelScan":
            if #available(iOS 16.0, *) {
                cancelRoomPlanScan()
            }
            result(nil)

        default:
            result(FlutterMethodNotImplemented)
        }
    }

    // MARK: - Device Info

    private func getDeviceModel() -> String {
        var systemInfo = utsname()
        uname(&systemInfo)
        let machineMirror = Mirror(reflecting: systemInfo.machine)
        let identifier = machineMirror.children.reduce("") { id, el in
            guard let v = el.value as? Int8, v != 0 else { return id }
            return id + String(UnicodeScalar(UInt8(v)))
        }
        let map: [String: String] = [
            "iPhone14,2": "iPhone 13 Pro", "iPhone14,3": "iPhone 13 Pro Max",
            "iPhone15,2": "iPhone 14 Pro", "iPhone15,3": "iPhone 14 Pro Max",
            "iPhone16,1": "iPhone 15 Pro", "iPhone16,2": "iPhone 15 Pro Max",
            "iPhone17,1": "iPhone 16 Pro", "iPhone17,2": "iPhone 16 Pro Max",
            "iPhone13,4": "iPhone 12 Pro", "iPhone13,3": "iPhone 12 Pro Max",
            "iPad13,4": "iPad Pro 11 M1", "iPad13,8": "iPad Pro 12.9 M1",
            "iPad14,3": "iPad Pro 11 M2", "iPad14,5": "iPad Pro 12.9 M2",
        ]
        return map[identifier] ?? "iPhone"
    }

    private func detectCapability() -> [String: Any] {
        var hasLidar = false
        var supportsRoomPlan = false
        if #available(iOS 13.4, *) {
            hasLidar = ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh)
        }
        if #available(iOS 16.0, *) {
            supportsRoomPlan = RoomCaptureSession.isSupported
        }
        return [
            "platform": "ios",
            "device_model": getDeviceModel(),
            "has_lidar": hasLidar,
            "has_depth_sensor": hasLidar,
            "supports_roomplan": supportsRoomPlan,
            "os_version": UIDevice.current.systemVersion,
            "device_name": UIDevice.current.name,
            "screen_width": UIScreen.main.bounds.width,
            "screen_height": UIScreen.main.bounds.height,
            "screen_scale": UIScreen.main.scale,
        ]
    }

    private func detectLidar() -> [String: Any] {
        if #available(iOS 13.4, *) {
            return ["available": ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh)]
        }
        return ["available": false]
    }

    // MARK: - RoomPlan (iOS 16+)

    @available(iOS 16.0, *)
    private func startRoomPlanScan(result: @escaping FlutterResult) {
        guard RoomCaptureSession.isSupported else {
            result(FlutterError(code: "UNSUPPORTED",
                message: "RoomPlan 需要 LiDAR 传感器", details: nil))
            return
        }

        scanResult = result

        let session = RoomCaptureSession()
        let builder = RoomBuilder(options: [.beautifyObjects])
        _captureSession = session
        _captureBuilder = builder

        let config = RoomCaptureSession.Configuration()
        session.run(configuration: config)
        session.delegate = self

        let tmpDir = NSTemporaryDirectory()
        tempUsdzPath = "\(tmpDir)scan_\(Int(Date().timeIntervalSince1970)).usdz"

        result(["status": "scanning", "message": "RoomPlan 扫描已启动"])
    }

    @available(iOS 16.0, *)
    private func cancelRoomPlanScan() {
        (_captureSession as? RoomCaptureSession)?.stop()
        _captureSession = nil
        _captureBuilder = nil
        scanResult = nil
    }

    @available(iOS 16.0, *)
    private func processResult(_ capturedRoom: CapturedRoom) throws -> [String: Any] {
        guard let usdzPath = tempUsdzPath else {
            throw NSError(domain: "ARScan", code: -1, userInfo: nil)
        }

        // 导出 USDZ
        try capturedRoom.export(to: URL(fileURLWithPath: usdzPath))

        // 提取门窗
        var doors: [[String: Any]] = []
        for door in capturedRoom.doors {
            let t = door.transform
            doors.append([
                "id": door.identifier.uuidString,
                "type": "door",
                "position": ["x": t.columns.3.x, "y": t.columns.3.y, "z": t.columns.3.z],
                "width": door.dimensions.x, "height": door.dimensions.y,
            ])
        }
        var windows: [[String: Any]] = []
        for window in capturedRoom.windows {
            let t = window.transform
            windows.append([
                "id": window.identifier.uuidString,
                "type": "window",
                "position": ["x": t.columns.3.x, "y": t.columns.3.y, "z": t.columns.3.z],
                "width": window.dimensions.x, "height": window.dimensions.y,
            ])
        }
        var openings: [[String: Any]] = []
        for opening in capturedRoom.openings {
            let t = opening.transform
            openings.append([
                "id": opening.identifier.uuidString,
                "type": "opening",
                "position": ["x": t.columns.3.x, "y": t.columns.3.y, "z": t.columns.3.z],
                "width": opening.dimensions.x, "height": opening.dimensions.y,
            ])
        }
        // 墙壁
        var walls: [[String: Any]] = []
        for wall in capturedRoom.walls {
            let t = wall.transform
            walls.append([
                "id": wall.identifier.uuidString,
                "position": ["x": t.columns.3.x, "y": t.columns.3.y, "z": t.columns.3.z],
                "length": wall.dimensions.x, "height": wall.dimensions.y,
            ])
        }
        // 物体
        var objects: [[String: Any]] = []
        for obj in capturedRoom.objects {
            let t = obj.transform
            objects.append([
                "id": obj.identifier.uuidString,
                "category": String(describing: obj.category),
                "position": ["x": t.columns.3.x, "y": t.columns.3.y, "z": t.columns.3.z],
                "width": obj.dimensions.x, "height": obj.dimensions.y, "depth": obj.dimensions.z,
            ])
        }

        let fileSize = (try? FileManager.default.attributesOfItem(atPath: usdzPath))?[.size] as? Int64 ?? 0

        return [
            "model_path": usdzPath,
            "model_format": "usdz",
            "file_size_bytes": fileSize,
            "doors": doors, "windows": windows, "openings": openings,
            "walls": walls, "objects": objects,
            "door_count": doors.count, "window_count": windows.count,
            "wall_count": walls.count, "object_count": objects.count,
            "total_area_sqm": 0.0, // iOS 16.0 CapturedRoom 无 rooms/floors 属性
        ]
    }
}

// MARK: - RoomCaptureSessionDelegate

extension ARScanPlugin: @preconcurrency RoomCaptureSessionDelegate {

    @available(iOS 16.0, *)
    func captureSession(_ session: RoomCaptureSession, didUpdate room: CapturedRoom) {
        DispatchQueue.main.async { [weak self] in
            self?.channel?.invokeMethod("onScanProgress", arguments: [
                "status": "progress",
                "door_count": room.doors.count,
                "window_count": room.windows.count,
                "wall_count": room.walls.count,
                "object_count": room.objects.count,
            ])
        }
    }

    @available(iOS 16.0, *)
    func captureSession(_ session: RoomCaptureSession, didEndWith data: CapturedRoomData, error: Error?) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            session.stop()

            if let error = error {
                self.channel?.invokeMethod("onScanError", arguments: error.localizedDescription)
                self.scanResult?(FlutterError(code: "SCAN_ERROR", message: error.localizedDescription, details: nil))
                self.scanResult = nil
                return
            }

            Task {
                do {
                    guard let finalRoom = try await (self._captureBuilder as? RoomBuilder)?.capturedRoom(from: data) else {
                        self.scanResult?(FlutterError(code: "BUILD_ERROR", message: "无法重建房间", details: nil))
                        self.scanResult = nil
                        return
                    }
                    let resultData = try self.processResult(finalRoom)
                    self.scanResult?(resultData)
                    self.scanResult = nil
                } catch {
                    self.channel?.invokeMethod("onScanError", arguments: error.localizedDescription)
                    self.scanResult?(FlutterError(code: "PROCESS_ERROR", message: error.localizedDescription, details: nil))
                    self.scanResult = nil
                }
            }
        }
    }

    @available(iOS 16.0, *)
    func captureSession(_ session: RoomCaptureSession, didProvide instruction: RoomCaptureSession.Instruction) {
        DispatchQueue.main.async { [weak self] in
            let msg = String(describing: instruction)
            var type = "unknown"
            if msg.contains("MoveAway") || msg.contains("move away") { type = "move_away_from_wall" }
            else if msg.contains("TurnOn") || msg.contains("light") { type = "turn_on_light" }
            else if msg.contains("LowTexture") || msg.contains("texture") { type = "low_texture" }
            self?.channel?.invokeMethod("onScanInstruction", arguments: [
                "type": type, "instruction": msg
            ])
        }
    }
}
