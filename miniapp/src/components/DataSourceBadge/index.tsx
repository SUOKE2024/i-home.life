import React from 'react';
import { View, Text } from '@tarojs/components';
import classnames from 'classnames';
import { useAppStore } from '@/store/useAppStore';
import styles from './index.module.scss';

interface DataSourceBadgeProps {
  className?: string;
  /** 长文案模式：附带降级原因（首页/我的使用，便于运营判断） */
  verbose?: boolean;
}

/**
 * 数据来源标识：仅在降级为演示数据时显示。
 * 生产数据（live）不显示任何标识，避免干扰正常浏览。
 */
const DataSourceBadge: React.FC<DataSourceBadgeProps> = ({ className, verbose = false }) => {
  const dataSource = useAppStore((state) => state.dataSource);
  const reason = useAppStore((state) => state.dataSourceReason);

  if (dataSource !== 'demo') return null;

  return (
    <View className={classnames(styles.badge, className)}>
      <View className={styles.dot} />
      <Text className={styles.text}>
        {verbose && reason ? `演示数据 · ${reason}` : '演示数据'}
      </Text>
    </View>
  );
};

export default DataSourceBadge;
