import React, { useMemo } from 'react';
import { View, Text, ScrollView } from '@tarojs/components';
import { useRouter } from '@tarojs/taro';
import styles from './index.module.scss';

interface Section {
  title: string;
  paragraphs: string[];
}

const PRIVACY_SECTIONS: Section[] = [
  {
    title: '一、我们收集的信息',
    paragraphs: [
      '1. 登录标识：您使用微信登录时，我们通过微信开放接口获取您的 openid（微信用户在本小程序内的唯一标识）与 unionid（若已关联开放平台）。我们不会获取您的微信密码。',
      '2. 手机号：仅在您主动点击「绑定手机号」并同意微信手机号快速验证时收集，用于账号联系与服务派单。您可拒绝授权，拒绝后仍可浏览非个性化内容。',
      '3. 空间与项目数据：您录入或由索克服务人员代录的空间资产信息（名称、城市、面积、业态）、改造项目进度、设备与场景配置。',
      '4. 设备与监测数据：空间内已接入的智能设备状态、控制指令记录，以及健康监测设备采集的指标（如心率、血氧、睡眠、步数）。',
      '5. 对话内容：您与 AI 管家的对话文本，用于生成回复与改进服务质量。',
      '6. 运行日志：页面访问、接口错误、性能指标等，用于故障排查与稳定性优化。'
    ]
  },
  {
    title: '二、我们如何使用信息',
    paragraphs: [
      '用于账号识别与登录状态维持、空间健康与智能化就绪度计算、改造项目进度展示、设备控制与场景执行、适老改造套餐与补贴预估测算、AI 咨询回复、服务派单与售后联系。',
      '我们不会将您的信息用于与上述目的无关的营销推送；如未来开展增值服务，将另行取得您的同意。'
    ]
  },
  {
    title: '三、信息的存储与保护',
    paragraphs: [
      '数据存储于中华人民共和国境内的服务器。传输过程使用 HTTPS 加密，登录凭证采用服务端签发的短期令牌，令牌到期自动失效。',
      '我们按最小必要原则控制内部访问权限，并对敏感操作留存审计日志。',
      '保存期限：账号存续期间保留；您注销账号后，除法律法规要求留存的记录外，将在 30 日内删除或匿名化处理。'
    ]
  },
  {
    title: '四、信息的共享与委托处理',
    paragraphs: [
      '微信（深圳市腾讯计算机系统有限公司）：用于登录鉴权与手机号验证。',
      '云服务与短信服务提供商：用于数据存储、备份与必要的通知下发。',
      '大模型服务提供商：AI 管家生成回复时，您的提问文本会经接口传输至模型服务方处理，我们要求其不得将数据用于模型训练。',
      '除上述情形及法律法规要求外，我们不会向第三方提供您的个人信息。'
    ]
  },
  {
    title: '五、您的权利',
    paragraphs: [
      '您可在「我的」页查看账号信息与绑定状态；可联系客服更正空间与项目信息；可申请删除特定数据或注销账号。',
      '撤回授权：您可在微信「设置 → 隐私 → 授权管理」中撤回手机号等授权，撤回后相关功能将不可用。'
    ]
  },
  {
    title: '六、未成年人保护',
    paragraphs: [
      '本小程序面向业主与家庭服务，若您为未满 14 周岁的未成年人，请在监护人陪同下使用，并由监护人代为同意本指引。'
    ]
  },
  {
    title: '七、联系我们',
    paragraphs: [
      '如对本指引有疑问、需查询或删除个人信息，可通过小程序内「我的 → 用户服务协议」所列联系方式与我们联系，我们将在 15 个工作日内答复。',
      '本指引的更新版本将在本页面公示，重大变更将以显著方式提示。'
    ]
  }
];

const TERMS_SECTIONS: Section[] = [
  {
    title: '一、服务内容',
    paragraphs: [
      '索克家居是面向存量空间的服务平台，提供空间资产评估、智能化改造交付、设备与场景运营、适老改造、健康监测接入等服务。平台角色为服务提供方，不持有、不经营您的房产。'
    ]
  },
  {
    title: '二、账号与使用规范',
    paragraphs: [
      '您应使用真实、有效的信息完成账号注册与手机号绑定，并对账号下的操作负责。',
      '不得利用本小程序从事违法活动、干扰平台正常运行、批量抓取数据或尝试越权访问他人空间与项目。'
    ]
  },
  {
    title: '三、数据与展示口径',
    paragraphs: [
      '空间健康指数由四维智能就绪度（设备接入 30 分、感知覆盖 25 分、场景编排 25 分、合规就绪 20 分）加权得出，仅统计真实接入的数据，未接入维度计 0 分。',
      '项目进度按阶段状态推断展示，实际完成情况以现场记录与验收文件为准。'
    ]
  },
  {
    title: '四、补贴预估的边界',
    paragraphs: [
      '适老改造补贴预估基于标准快装套餐一口价与全国基准政策档案测算，不判定个人资格，不代表主管部门核定结果。',
      '地方补贴目录、比例与单件上限可能调整，签约前请向当地主管部门核实最新申报口径。'
    ]
  },
  {
    title: '五、健康与 AI 内容免责',
    paragraphs: [
      '健康监测数据来自空间内设备采集，仅作趋势参考，不构成医疗诊断或治疗建议。如出现紧急健康状况，请立即联系医疗机构或拨打急救电话。',
      'AI 管家回复由模型生成或引自知识库，可能存在偏差，不构成设计、施工、法律或医疗承诺。'
    ]
  },
  {
    title: '六、服务变更与终止',
    paragraphs: [
      '平台可能因业务调整、政策变化或系统维护暂停部分功能，将提前在显著位置告知。',
      '您可随时停止使用并注销账号；注销后历史数据按隐私保护指引处理。'
    ]
  },
  {
    title: '七、争议解决',
    paragraphs: [
      '本协议适用中华人民共和国法律。因本协议产生的争议，双方应友好协商；协商不成的，提交平台所在地有管辖权的人民法院处理。'
    ]
  }
];

const AgreementPage: React.FC = () => {
  const router = useRouter();
  const type = router.params.type === 'terms' ? 'terms' : 'privacy';
  const isPrivacy = type === 'privacy';

  const sections = useMemo(() => (isPrivacy ? PRIVACY_SECTIONS : TERMS_SECTIONS), [isPrivacy]);

  return (
    <View className={styles.page}>
      <ScrollView className={styles.scroll} scrollY>
        <Text className={styles.title}>{isPrivacy ? '索克家居隐私保护指引' : '索克家居用户服务协议'}</Text>
        <Text className={styles.updated}>更新日期：2026-10-24 · 生效日期：2026-10-24</Text>
        <Text className={styles.intro}>
          {isPrivacy
            ? '我们深知个人信息对您的重要性。本指引说明索克家居小程序收集哪些信息、为何收集、如何保护，以及您可以如何管理这些信息。请在授权前仔细阅读。'
            : '欢迎使用索克家居小程序。本协议约定您与平台之间的权利义务，重点说明服务边界、数据口径与责任限制。继续使用即表示您已阅读并同意本协议。'}
        </Text>

        {sections.map((section) => (
          <View key={section.title} className={styles.section}>
            <Text className={styles.sectionTitle}>{section.title}</Text>
            {section.paragraphs.map((paragraph) => (
              <Text key={paragraph} className={styles.paragraph}>
                {paragraph}
              </Text>
            ))}
          </View>
        ))}

        <Text className={styles.footer}>
          索克家居 · 空间健康资产运营商{'\n'}如对以上内容有异议，请停止使用并联系我们。
        </Text>
      </ScrollView>
    </View>
  );
};

export default AgreementPage;
