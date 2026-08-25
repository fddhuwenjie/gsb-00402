import { Row, Col, Spin, Tag } from 'antd'
import {
  ExperimentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  FileSearchOutlined,
  FunctionOutlined,
} from '@ant-design/icons'
import { useState, useEffect } from 'react'
import { dashboardApi } from '../api/client'

export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    dashboardApi.stats()
      .then((res) => setStats(res.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>

  const cards = [
    { label: '分析任务总数', value: stats?.total_analyses || 0, icon: <ExperimentOutlined />, color: '#1677ff' },
    { label: '已完成分析', value: stats?.completed_analyses || 0, icon: <CheckCircleOutlined />, color: '#52c41a' },
    { label: '失败分析', value: stats?.failed_analyses || 0, icon: <CloseCircleOutlined />, color: '#ff4d4f' },
    { label: '特征文件数', value: stats?.total_signatures || 0, icon: <FileSearchOutlined />, color: '#722ed1' },
    { label: '特征函数总数', value: stats?.total_functions || 0, icon: <FunctionOutlined />, color: '#fa8c16' },
  ]

  const riskColors = { high: '#ff4d4f', medium: '#faad14', low: '#52c41a', info: '#1677ff', none: '#d9d9d9' }
  const riskLabels = { high: '高风险', medium: '中风险', low: '低风险', info: '信息', none: '无风险' }

  return (
    <div>
      <div className="page-header"><h2>仪表盘</h2></div>
      <Row gutter={[16, 16]}>
        {cards.map((card, i) => (
          <Col xs={24} sm={12} md={8} lg={24/5} xl={24/5} style={{ flex: '1 1 20%', maxWidth: '20%' }} key={i}>
            <div className="stat-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div className="stat-number" style={{ color: card.color }}>{card.value}</div>
                  <div className="stat-label">{card.label}</div>
                </div>
                <div style={{ fontSize: 36, color: card.color, opacity: 0.2 }}>{card.icon}</div>
              </div>
            </div>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} md={12}>
          <div className="stat-card">
            <h3 style={{ marginBottom: 16 }}>风险分布</h3>
            {stats?.recent_risk_distribution && Object.keys(stats.recent_risk_distribution).length > 0 ? (
              Object.entries(stats.recent_risk_distribution).map(([level, count]) => (
                <div key={level} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <Tag color={riskColors[level] || '#d9d9d9'}>{riskLabels[level] || level}</Tag>
                  <span style={{ fontSize: 18, fontWeight: 600 }}>{count}</span>
                </div>
              ))
            ) : (
              <div style={{ color: '#999', textAlign: 'center', padding: 24 }}>暂无数据</div>
            )}
          </div>
        </Col>
        <Col xs={24} md={12}>
          <div className="stat-card">
            <h3 style={{ marginBottom: 16 }}>语言分布</h3>
            {stats?.language_distribution && Object.keys(stats.language_distribution).length > 0 ? (
              Object.entries(stats.language_distribution).map(([lang, count]) => (
                <div key={lang} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <Tag color="blue">{lang.toUpperCase()}</Tag>
                  <span style={{ fontSize: 18, fontWeight: 600 }}>{count}</span>
                </div>
              ))
            ) : (
              <div style={{ color: '#999', textAlign: 'center', padding: 24 }}>暂无数据</div>
            )}
          </div>
        </Col>
      </Row>
    </div>
  )
}
