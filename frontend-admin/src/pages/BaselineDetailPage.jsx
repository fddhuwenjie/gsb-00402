import { Descriptions, Spin, Tag, Table, Button, Empty, Typography } from 'antd'
import { ArrowLeftOutlined, DiffOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { baselineApi } from '../api/client'

const { Text } = Typography

const riskColors = { high: 'red', medium: 'orange', low: 'green', info: 'blue', none: 'default' }
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }

export default function BaselineDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    baselineApi.get(id)
      .then((res) => setDetail(res.data))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!detail) return <div style={{ textAlign: 'center', padding: 80 }}>未找到基线</div>

  const assetColumns = [
    { title: '文件', dataIndex: 'file', ellipsis: true, width: 220 },
    {
      title: '语言', dataIndex: 'language', width: 80, align: 'center',
      render: (v) => <Tag color="blue">{v?.toUpperCase()}</Tag>,
    },
    {
      title: '算法/库', dataIndex: 'algorithm_name', width: 140,
      render: (v, r) => <><Text strong>{v}</Text><br /><Text type="secondary" style={{ fontSize: 12 }}>{r.algorithm}</Text></>,
    },
    {
      title: '函数签名', dataIndex: 'signature', width: 220, ellipsis: true,
      render: (v) => <code style={{ fontSize: 12 }}>{v}</code>,
    },
    {
      title: '风险级别', dataIndex: 'risk_level', width: 90, align: 'center',
      render: (v) => <Tag color={riskColors[v] || 'default'}>{riskLabels[v] || v}</Tag>,
    },
    { title: '出现次数', dataIndex: 'occurrences', width: 90, align: 'center' },
    {
      title: '行号', dataIndex: 'lines', width: 160,
      render: (lines) => lines?.map((l) => <Tag key={l} style={{ marginBottom: 2 }}>{l}</Tag>),
    },
    {
      title: '置信度', dataIndex: 'confidence', width: 90, align: 'center',
      render: (v) => `${Math.round(v * 100)}%`,
    },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/baselines')}>返回</Button>
        <h2>基线详情</h2>
        <Button
          type="primary"
          icon={<DiffOutlined />}
          style={{ marginLeft: 'auto' }}
          onClick={() => navigate(`/diffs/new?baseline_id=${detail.id}`)}
        >
          生成差异报告
        </Button>
      </div>

      <div className="report-section">
        <Descriptions bordered column={2} title="基线信息">
          <Descriptions.Item label="基线名称">{detail.name}</Descriptions.Item>
          <Descriptions.Item label="风险级别">
            <Tag color={riskColors[detail.risk_level]}>{riskLabels[detail.risk_level] || detail.risk_level}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="代码语言"><Tag color="blue">{detail.language?.toUpperCase()}</Tag></Descriptions.Item>
          <Descriptions.Item label="密码资产数">{detail.total_assets}</Descriptions.Item>
          <Descriptions.Item label="来源分析">
            <a onClick={() => navigate(`/analyses/${detail.task_id}`)}>{detail.task_name || `#${detail.task_id}`}</a>
          </Descriptions.Item>
          <Descriptions.Item label="创建者">{detail.creator_name}</Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>{detail.description || '—'}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
        </Descriptions>
      </div>

      <div className="report-section">
        <h3 style={{ marginBottom: 16 }}>基线密码资产快照（{detail.assets?.length || 0}）</h3>
        {detail.assets?.length > 0 ? (
          <Table
            dataSource={detail.assets}
            columns={assetColumns}
            rowKey="key"
            size="small"
            scroll={{ x: 1100 }}
            pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条资产` }}
          />
        ) : (
          <Empty description="该基线未记录任何密码资产" />
        )}
      </div>
    </div>
  )
}
