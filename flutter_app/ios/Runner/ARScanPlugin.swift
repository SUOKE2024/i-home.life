import Flutter
import UIKit
import ARKit
import RoomPlan

/// AR 空间测量原生插件 — RoomPlan (iOS 16+)
///
/// v1.2.x 协议修复 (P0-1):
///  - startScan 仅返回 {status: "scanning"} 即时确认, 不再消费最终 FlutterResult;
///  - 扫描结果通过事件通道 `onScanCompleted` / `onScanError` 交付给 Dart,
///    修复"假成功"(startScan 即时返回被当作最终结果, 真实 USDZ 数据永远丢失)与
///    同一 FlutterResult 被调用两次的违约问题;
///  - 新增 RoomCaptureViewController 展示系统捕获界面(摄像头画面 + 引导),
///    提供「完成扫描」/「取消」操作, 用户可真正完成扫描而不是盲扫。
class ARScanPlugin: NSObject {

    static let channelName = "com.ihome.life/ar_scan"

    private var channel: FlutterMethodChannel?
    private var tempUsdzPath: String?
    private var scanStartedAt: Date?

    // RoomPlan 对象通过 Any? 存储以避免编译时类型检查
    private var _captureSession: Any?
    private var _captureBuilder: Any?
    private var _captureViewController: UIViewController?

    // 用户取消标记: 取消后 didEndWith 不再处理数据
    private var isScanCancelled = false

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

        let builder = RoomBuilder(options: [.beautifyObjects])
        _captureBuilder = builder
        isScanCancelled = false
        scanStartedAt = Date()

        let config = RoomCaptureSession.Configuration()

        let tmpDir = NSTemporaryDirectory()
        tempUsdzPath = "\(tmpDir)scan_\(Int(Date().timeIntervalSince1970)).usdz"

        // 展示系统捕获界面: 摄像头画面 + RoomPlan 引导 + 完成/取消按钮
        // iOS 26 SDK: RoomCaptureView 自持 RoomCaptureSession, 由视图内部创建后统一运行
        presentRoomCaptureUI(configuration: config)

        // 仅作即时确认, 不消费最终结果 (最终结果走 onScanCompleted 事件)
        result(["status": "scanning", "message": "RoomPlan 扫描已启动"])
    }

    @available(iOS 16.0, *)
    private func cancelRoomPlanScan() {
        isScanCancelled = true
        (_captureSession as? RoomCaptureSession)?.stop()
        dismissCaptureUI()
        _captureSession = nil
        _captureBuilder = nil
        _captureViewController = nil
    }

    // MARK: - 捕获界面展示

    @available(iOS 16.0, *)
    private func presentRoomCaptureUI(configuration: RoomCaptureSession.Configuration) {
        guard _captureViewController == nil,
              let top = ARScanPlugin.topViewController() else { return }

        let viewController = RoomCaptureViewController(
            configuration: configuration,
            sessionDelegate: self,
            onSessionReady: { [weak self] session in
                self?._captureSession = session
            },
            onFinish: { [weak self] in
                // 完成扫描 → stop() 触发 didEndWith, 由插件统一收尾
                (self?._captureSession as? RoomCaptureSession)?.stop()
            },
            onCancel: { [weak self] in
                self?.cancelRoomPlanScan()
                self?.channel?.invokeMethod("onScanCancelled", arguments: nil)
            }
        )
        _captureViewController = viewController
        top.present(viewController, animated: true)
    }

    private func dismissCaptureUI() {
        guard let vc = _captureViewController else { return }
        _captureViewController = nil
        vc.dismiss(animated: true)
    }

    /// 获取当前最顶层的可 present 控制器 (兼容 SceneDelegate / 多窗口)
    static func topViewController() -> UIViewController? {
        let scenes = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
        guard let window = scenes
            .flatMap({ $0.windows })
            .first(where: { $0.isKeyWindow }) else { return nil }

        var top = window.rootViewController
        while let presented = top?.presentedViewController {
            top = presented
        }
        if top is FlutterViewController { return top }
        // Flutter 视图可能被包在容器控制器中
        while let nav = top as? UINavigationController {
            top = nav.visibleViewController ?? nav
        }
        return top
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

        // 扫描耗时 (秒)
        let durationSec = Int(Date().timeIntervalSince(scanStartedAt ?? Date()))

        return [
            "model_path": usdzPath,
            "model_format": "usdz",
            "file_size_bytes": fileSize,
            "doors": doors, "windows": windows, "openings": openings,
            "walls": walls, "objects": objects,
            "door_count": doors.count, "window_count": windows.count,
            "wall_count": walls.count, "object_count": objects.count,
            "points_count": walls.count * 2000 + objects.count * 1000, // 估算: RoomPlan 不导出原始点云, 真实几何以 USDZ mesh 为准
            "duration_sec": durationSec,
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
            self.dismissCaptureUI()

            // 用户主动取消: 不再处理数据
            if self.isScanCancelled {
                self.isScanCancelled = false
                self._captureSession = nil
                self._captureBuilder = nil
                return
            }
            self.isScanCancelled = false

            if let error = error {
                self.channel?.invokeMethod("onScanError", arguments: error.localizedDescription)
                self._captureSession = nil
                self._captureBuilder = nil
                return
            }

            Task {
                do {
                    guard let finalRoom = try await (self._captureBuilder as? RoomBuilder)?.capturedRoom(from: data) else {
                        self.channel?.invokeMethod("onScanError", arguments: "无法重建房间模型")
                        self._captureSession = nil
                        self._captureBuilder = nil
                        return
                    }
                    let resultData = try self.processResult(finalRoom)
                    // 真实扫描结果经事件通道交付给 Dart (v1.2.x P0-1 修复)
                    self.channel?.invokeMethod("onScanCompleted", arguments: resultData)
                    self._captureSession = nil
                    self._captureBuilder = nil
                } catch {
                    self.channel?.invokeMethod("onScanError", arguments: error.localizedDescription)
                    self._captureSession = nil
                    self._captureBuilder = nil
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

// MARK: - 系统 RoomPlan 捕获界面

/// 全屏展示 RoomCaptureView (摄像头画面 + 引导) 与 完成/取消 操作
@available(iOS 16.0, *)
final class RoomCaptureViewController: UIViewController {
    private let configuration: RoomCaptureSession.Configuration
    private weak var sessionDelegate: RoomCaptureSessionDelegate?
    private let onSessionReady: (RoomCaptureSession) -> Void
    private let onFinish: () -> Void
    private let onCancel: () -> Void
    private var captureView: RoomCaptureView?

    init(configuration: RoomCaptureSession.Configuration,
         sessionDelegate: RoomCaptureSessionDelegate,
         onSessionReady: @escaping (RoomCaptureSession) -> Void,
         onFinish: @escaping () -> Void,
         onCancel: @escaping () -> Void) {
        self.configuration = configuration
        self.sessionDelegate = sessionDelegate
        self.onSessionReady = onSessionReady
        self.onFinish = onFinish
        self.onCancel = onCancel
        super.init(nibName: nil, bundle: nil)
        modalPresentationStyle = .fullScreen
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        // 系统捕获视图: 摄像头实时画面 + RoomPlan 扫描引导
        // iOS 26 SDK: RoomCaptureView 自持 RoomCaptureSession, 通过 captureSession 获取后运行
        let captureView = RoomCaptureView(frame: view.bounds)
        captureView.delegate = self
        if let captureSession = captureView.captureSession {
            captureSession.delegate = sessionDelegate
            captureSession.run(configuration: configuration)
            onSessionReady(captureSession)
        }
        view.addSubview(captureView)
        captureView.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            captureView.topAnchor.constraint(equalTo: view.topAnchor),
            captureView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            captureView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            captureView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
        ])
        self.captureView = captureView

        // 底部操作栏
        let stack = UIStackView()
        stack.axis = .horizontal
        stack.distribution = .fillEqually
        stack.spacing = 16

        let cancelButton = makeButton(title: "取消", color: .systemRed)
        cancelButton.addTarget(self, action: #selector(cancelTapped), for: .touchUpInside)

        let finishButton = makeButton(title: "完成扫描", color: .systemGreen)
        finishButton.addTarget(self, action: #selector(finishTapped), for: .touchUpInside)

        stack.addArrangedSubview(cancelButton)
        stack.addArrangedSubview(finishButton)

        view.addSubview(stack)
        stack.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            stack.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -24),
            stack.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),
            stack.heightAnchor.constraint(equalToConstant: 56),
        ])
    }

    @objc private func finishTapped() { onFinish() }
    @objc private func cancelTapped() { onCancel() }

    private func makeButton(title: String, color: UIColor) -> UIButton {
        let button = UIButton(type: .system)
        button.setTitle(title, for: .normal)
        button.titleLabel?.font = .systemFont(ofSize: 18, weight: .semibold)
        button.backgroundColor = color.withAlphaComponent(0.25)
        button.layer.cornerRadius = 14
        button.tintColor = color
        return button
    }
}

@available(iOS 16.0, *)
extension RoomCaptureViewController: RoomCaptureViewDelegate {
    func captureView(_ captureView: RoomCaptureView, didPresent session: RoomCaptureSession) {}
    func captureView(_ captureView: RoomCaptureView, didStart session: RoomCaptureSession) {}
    func captureView(_ captureView: RoomCaptureView, didStop session: RoomCaptureSession) {}
    func captureView(_ captureView: RoomCaptureView, didFail session: RoomCaptureSession, error: Error) {}
}
