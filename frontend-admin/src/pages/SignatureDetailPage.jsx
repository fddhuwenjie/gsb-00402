import { Descriptions, Spin, Tag, Collapse, Table, Button } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { signatureApi } from '../api/client'

export default function SignatureDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    signatureApi.get(id)
      .then((res) => setDetail(res.data))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!detail) return <div style={{ textAlign: 'center', padding: 80 }}>未找到特征文件</div>

  const sigColumns = [
    { title: '标识符', dataIndex: 'identifier', width: 120 },
    { title: '模式', dataIndex: 'pattern', ellipsis: true },
    { title: '前缀', dataIndex: 'prefix', width: 180 },
  ]

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/signatures')}>返回</Button>
        <h2>特征文件详情</h2>
      </div>

      <div className="report-section">
        <Descriptions bordered column={2}>
          <Descriptions.Item label="名称">{detail.name}</Descriptions.Item>
          <Descriptions.Item label="原始文件名">{detail.original_filename}</Descriptions.Item>
          <Descriptions.Item label="规则数">{detail.rule_count}</Descriptions.Item>
          <Descriptions.Item label="函数数">{detail.function_count}</Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>{detail.description || '-'}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
        </Descriptions>
      </div>

      <div className="report-section">
        <h3 style={{ marginBottom: 16 }}>规则列表</h3>
        <Collapse
          items={(detail.rules || []).map((rule, idx) => ({
            key: idx,
            label: (
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <strong>{rule.name}</strong>
                <Tag color="blue">{rule.signatures?.length || 0} 个签名</Tag>
                {rule.description && <span style={{ color: '#999' }}>{rule.description}</span>}
              </div>
            ),
            children: (
              <Table
                dataSource={rule.signatures || []}
                columns={sigColumns}
                rowKey="identifier"
                size="small"
                pagination={false}
              />
            ),
          }))}
        />
      </div>
    </div>
  )
}
