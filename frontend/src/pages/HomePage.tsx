import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="px-4 py-8">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          播客制作前端流程验证系统
        </h1>
        <p className="text-lg text-gray-600 mb-8">
          从主题到书籍到资料收集的完整链路验证
        </p>

        <div className="bg-white shadow rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            核心功能
          </h2>
          <div className="space-y-4">
            <div>
              <h3 className="font-medium text-gray-900">1. 书单获取</h3>
              <p className="text-sm text-gray-600">
                支持 Amazon 畅销榜抓取和 CSV 导入
              </p>
            </div>
            <div>
              <h3 className="font-medium text-gray-900">2. 主题筛选</h3>
              <p className="text-sm text-gray-600">
                基于用户关注主题筛选候选书籍
              </p>
            </div>
            <div>
              <h3 className="font-medium text-gray-900">3. 资料检索</h3>
              <p className="text-sm text-gray-600">
                检索书评、访谈、出版信息等多源资料
              </p>
            </div>
            <div>
              <h3 className="font-medium text-gray-900">4. 充分度评估</h3>
              <p className="text-sm text-gray-600">
                评估主题匹配度和资料充分度
              </p>
            </div>
          </div>
        </div>

        <div className="flex space-x-4">
          <Link
            to="/books"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            开始使用
          </Link>
          <a
            href="https://github.com/yourusername/book-podcast-research"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            查看文档
          </a>
        </div>

        <div className="mt-8 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-yellow-800 mb-2">
            当前限制
          </h3>
          <ul className="text-sm text-yellow-700 space-y-1 list-disc list-inside">
            <li>Amazon 抓取依赖公开榜单结构</li>
            <li>LLM 判断存在主观性，需要人工复核</li>
            <li>Tavily 搜索受限于公开可访问内容</li>
            <li>书评充分度判断是辅助性的</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
