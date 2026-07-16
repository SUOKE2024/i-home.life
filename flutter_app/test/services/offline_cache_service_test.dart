import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:ihome_app/services/offline_cache_service.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  // ── 单例模式 ──

  group('单例模式', () {
    test('返回同一个实例', () {
      final a = OfflineCacheService();
      final b = OfflineCacheService();
      expect(identical(a, b), isTrue);
    });
  });

  // ── 缓存读写 ──

  group('缓存读写', () {
    test('cacheData 后 getCachedData 返回相同数据', () async {
      final service = OfflineCacheService();
      await service.cacheData('test-key', {'name': 'test', 'value': 42});

      final cached = await service.getCachedData('test-key');
      expect(cached, isNotNull);
      expect(cached!['name'], 'test');
      expect(cached['value'], 42);
    });

    test('getCachedData 无缓存返回 null', () async {
      final service = OfflineCacheService();
      final cached = await service.getCachedData('non-existent-key');
      expect(cached, isNull);
    });

    test('缓存支持列表类型', () async {
      final service = OfflineCacheService();
      await service.cacheData('list-key', [1, 2, 3, 'four']);

      final cached = await service.getCachedData('list-key');
      expect(cached, isA<List>());
      expect(cached, [1, 2, 3, 'four']);
    });

    test('缓存支持字符串类型', () async {
      final service = OfflineCacheService();
      await service.cacheData('string-key', 'hello world');

      final cached = await service.getCachedData('string-key');
      expect(cached, 'hello world');
    });

    test('缓存支持数值类型', () async {
      final service = OfflineCacheService();
      await service.cacheData('num-key', 123.45);

      final cached = await service.getCachedData('num-key');
      expect(cached, 123.45);
    });
  });

  // ── 缓存删除 ──

  group('缓存删除', () {
    test('remove 后 getCachedData 返回 null', () async {
      final service = OfflineCacheService();
      await service.cacheData('remove-key', {'data': 'to-remove'});
      // 确认已缓存
      expect(await service.getCachedData('remove-key'), isNotNull);

      await service.remove('remove-key');
      expect(await service.getCachedData('remove-key'), isNull);
    });

    test('remove 不存在的 key 不报错', () async {
      final service = OfflineCacheService();
      await service.remove('never-existed');
      // 不应抛异常
    });
  });

  // ── 同步队列 ──

  group('同步队列', () {
    test('enqueueSyncOperation 后 getSyncQueue 返回操作列表', () async {
      final service = OfflineCacheService();
      await service.enqueueSyncOperation({
        'action': 'create',
        'endpoint': '/projects',
      });

      final queue = await service.getSyncQueue();
      expect(queue.length, 1);
      expect(queue.first['action'], 'create');
      expect(queue.first['endpoint'], '/projects');
      expect(queue.first['queued_at'], isNotNull);
      expect(queue.first['retry_count'], 0);
    });

    test('syncQueueLength 返回正确长度', () async {
      final service = OfflineCacheService();
      expect(await service.syncQueueLength, 0);

      await service.enqueueSyncOperation({'op': 1});
      expect(await service.syncQueueLength, 1);

      await service.enqueueSyncOperation({'op': 2});
      expect(await service.syncQueueLength, 2);
    });

    test('removeSyncOperation 按索引移除', () async {
      final service = OfflineCacheService();
      await service.enqueueSyncOperation({'op': 'first'});
      await service.enqueueSyncOperation({'op': 'second'});
      await service.enqueueSyncOperation({'op': 'third'});

      await service.removeSyncOperation(1); // 移除 second

      final queue = await service.getSyncQueue();
      expect(queue.length, 2);
      expect(queue[0]['op'], 'first');
      expect(queue[1]['op'], 'third');
    });

    test('removeSyncOperation 越界索引无副作用', () async {
      final service = OfflineCacheService();
      await service.enqueueSyncOperation({'op': 'only'});

      await service.removeSyncOperation(99); // 越界
      expect(await service.syncQueueLength, 1);

      await service.removeSyncOperation(-1); // 负数索引
      expect(await service.syncQueueLength, 1);
    });

    test('clearSyncQueue 清空队列', () async {
      final service = OfflineCacheService();
      await service.enqueueSyncOperation({'op': 1});
      await service.enqueueSyncOperation({'op': 2});
      expect(await service.syncQueueLength, 2);

      await service.clearSyncQueue();
      expect(await service.syncQueueLength, 0);

      final queue = await service.getSyncQueue();
      expect(queue, isEmpty);
    });
  });
}
