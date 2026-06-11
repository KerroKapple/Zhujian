"""
========================================
查询日志数据访问层 (Repository)
========================================

📚 模块说明：
- 封装查询日志的数据库操作
- 提供查询分析和统计功能
- 管理用户反馈

🎯 核心功能：
1. 查询日志的增删改查
2. 查询统计和分析
3. 用户反馈管理

========================================
"""
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta, timezone

from models.query import QueryLog, QueryFeedback
from core.constants import QueryType, AnswerQuality, RetrievalMode
from core.logger import logger


class QueryLogRepository:
    """
    查询日志数据访问类

    🎯 职责：
    - 记录用户查询
    - 分析查询效果
    - 统计热门查询
    """

    def __init__(self, session: Session):
        """
        初始化Repository

        参数：
            session: SQLAlchemy数据库会话
        """
        self.session = session

    # =========================================
    # 查询日志基本操作
    # =========================================

    def create_query_log(
            self,
            query: str,
            user_id: Optional[str] = None,
            **kwargs
    ) -> QueryLog:
        """
        创建查询日志

        参数：
            query: 查询问题
            user_id: 用户ID（可选）
            **kwargs: 其他字段

        返回：
            QueryLog: 创建的查询日志对象

        示例：
            log = repo.create_query_log(
                query="防水规范是什么？",
                user_id="user_123",
                query_type=QueryType.STANDARD_QUERY,
                retrieval_mode=RetrievalMode.HYBRID
            )
        """
        try:
            query_log = QueryLog(
                query=query,
                user_id=user_id,
                **kwargs
            )

            self.session.add(query_log)
            self.session.commit()
            self.session.refresh(query_log)

            logger.info(f"创建查询日志成功: {query_log.id}")
            return query_log

        except Exception as e:
            self.session.rollback()
            logger.error(f"创建查询日志失败: {str(e)}")
            raise

    def get_query_log_by_id(self, log_id: str) -> Optional[QueryLog]:
        """
        根据ID获取查询日志

        参数：
            log_id: 查询日志ID

        返回：
            QueryLog: 查询日志对象
        """
        try:
            query_log = self.session.query(QueryLog).filter(
                QueryLog.id == log_id
            ).first()
            return query_log
        except Exception as e:
            logger.error(f"获取查询日志失败: {str(e)}")
            raise

    def _apply_query_log_update(
            self,
            log_id: str,
            **kwargs
    ) -> Optional[QueryLog]:
        """
        无副作用 setter：仅写入内存对象字段，不 commit/不 rollback。
        由调用方统一管理事务。
        """
        query_log = self.get_query_log_by_id(log_id)
        if not query_log:
            logger.warning(f"查询日志不存在: {log_id}")
            return None

        for key, value in kwargs.items():
            if hasattr(query_log, key):
                setattr(query_log, key, value)

        return query_log

    def update_query_log(
            self,
            log_id: str,
            **kwargs
    ) -> Optional[QueryLog]:
        """
        更新查询日志（自带事务提交）

        参数：
            log_id: 查询日志ID
            **kwargs: 要更新的字段

        返回：
            QueryLog: 更新后的查询日志

        示例：
            # 更新查询结果和性能指标
            log = repo.update_query_log(
                log_id="log_123",
                answer="根据规范...",
                retrieval_time=0.5,
                generation_time=1.2,
                total_time=1.7,
                retrieved_count=5
            )
        """
        try:
            query_log = self._apply_query_log_update(log_id, **kwargs)
            if not query_log:
                return None

            self.session.commit()
            self.session.refresh(query_log)

            return query_log

        except Exception as e:
            self.session.rollback()
            logger.error(f"更新查询日志失败: {str(e)}")
            raise

    # =========================================
    # 查询日志查询
    # =========================================

    def list_query_logs(
            self,
            user_id: Optional[str] = None,
            query_type: Optional[QueryType] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            skip: int = 0,
            limit: int = 20
    ) -> List[QueryLog]:
        """
        列出查询日志

        参数：
            user_id: 用户ID过滤
            query_type: 查询类型过滤
            start_date: 开始日期
            end_date: 结束日期
            skip: 跳过的记录数
            limit: 返回的最大记录数

        返回：
            List[QueryLog]: 查询日志列表
        """
        try:
            query = self.session.query(QueryLog)

            # 应用过滤条件
            if user_id:
                query = query.filter(QueryLog.user_id == user_id)
            if query_type:
                query = query.filter(QueryLog.query_type == query_type)
            if start_date:
                query = query.filter(QueryLog.created_at >= start_date)
            if end_date:
                query = query.filter(QueryLog.created_at <= end_date)

            # 按时间倒序排列
            query = query.order_by(desc(QueryLog.created_at))

            # 分页
            logs = query.offset(skip).limit(limit).all()

            return logs

        except Exception as e:
            logger.error(f"列出查询日志失败: {str(e)}")
            raise

    def search_query_logs(
            self,
            keyword: str,
            skip: int = 0,
            limit: int = 20
    ) -> List[QueryLog]:
        """
        搜索查询日志（按查询内容）

        参数：
            keyword: 搜索关键词
            skip: 跳过的记录数
            limit: 返回的最大记录数

        返回：
            List[QueryLog]: 匹配的查询日志列表
        """
        try:
            search_pattern = f"%{keyword}%"

            logs = self.session.query(QueryLog).filter(
                QueryLog.query.like(search_pattern)
            ).order_by(
                desc(QueryLog.created_at)
            ).offset(skip).limit(limit).all()

            return logs

        except Exception as e:
            logger.error(f"搜索查询日志失败: {str(e)}")
            raise

    # =========================================
    # 用户反馈操作
    # =========================================

    def create_feedback(
            self,
            query_log_id: str,
            rating: int,
            is_helpful: bool,
            user_id: Optional[str] = None,
            **kwargs
    ) -> QueryFeedback:
        """
        创建查询反馈

        参数：
            query_log_id: 查询日志ID
            rating: 评分（1-5星）
            is_helpful: 是否有帮助
            user_id: 用户ID
            **kwargs: 其他字段

        返回：
            QueryFeedback: 创建的反馈对象

        示例：
            feedback = repo.create_feedback(
                query_log_id="log_123",
                rating=5,
                is_helpful=True,
                user_id="user_123",
                comment="答案非常准确！"
            )
        """
        try:
            feedback = QueryFeedback(
                query_log_id=query_log_id,
                rating=rating,
                is_helpful=is_helpful,
                user_id=user_id,
                **kwargs
            )

            self.session.add(feedback)

            # 同步查询日志反馈字段（无副作用 setter，由本方法末尾统一提交）
            self._apply_query_log_update(
                query_log_id,
                user_rating=rating,
                is_helpful=is_helpful
            )

            self.session.commit()
            self.session.refresh(feedback)

            logger.info(f"创建查询反馈成功: {feedback.id}")
            return feedback

        except Exception as e:
            self.session.rollback()
            logger.error(f"创建查询反馈失败: {str(e)}")
            raise

    # =========================================
    # 统计分析
    # =========================================

    def get_query_statistics(
            self,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取查询统计信息

        参数：
            start_date: 开始日期
            end_date: 结束日期

        返回：
            Dict: 统计数据
        """
        try:
            query = self.session.query(QueryLog)

            # 时间范围过滤
            if start_date:
                query = query.filter(QueryLog.created_at >= start_date)
            if end_date:
                query = query.filter(QueryLog.created_at <= end_date)

            stats = {
                "total_queries": query.count(),
                # 成功口径：有答案且无错误，与 failed_queries 不重叠
                "successful_queries": query.filter(
                    QueryLog.has_answer == True,
                    QueryLog.has_error == False
                ).count(),
                "failed_queries": query.filter(QueryLog.has_error == True).count(),
                "avg_total_time": 0,
                "avg_retrieval_time": 0,
                "avg_generation_time": 0,
                "avg_rating": 0,
                "by_type": {},
                "by_mode": {}
            }

            # 计算平均时间
            avg_times = self.session.query(
                func.avg(QueryLog.total_time).label("avg_total"),
                func.avg(QueryLog.retrieval_time).label("avg_retrieval"),
                func.avg(QueryLog.generation_time).label("avg_generation")
            ).first()

            if avg_times:
                stats["avg_total_time"] = float(avg_times.avg_total or 0)
                stats["avg_retrieval_time"] = float(avg_times.avg_retrieval or 0)
                stats["avg_generation_time"] = float(avg_times.avg_generation or 0)

            # 计算平均评分
            avg_rating = self.session.query(
                func.avg(QueryLog.user_rating)
            ).filter(QueryLog.user_rating.isnot(None)).scalar()

            stats["avg_rating"] = float(avg_rating or 0)

            # 按查询类型统计
            for query_type in QueryType:
                count = query.filter(QueryLog.query_type == query_type).count()
                stats["by_type"][query_type.value] = count

            # 按检索模式统计
            for mode in RetrievalMode:
                count = query.filter(QueryLog.retrieval_mode == mode).count()
                stats["by_mode"][mode.value] = count

            return stats

        except Exception as e:
            logger.error(f"获取查询统计失败: {str(e)}")
            raise

    def get_hot_queries(
            self,
            limit: int = 10,
            days: int = 7
    ) -> List[Tuple[str, int]]:
        """
        获取热门查询

        参数：
            limit: 返回的最大数量
            days: 统计最近几天的数据

        返回：
            List[Tuple]: (查询内容, 查询次数) 的列表
        """
        try:
            # 计算起始日期
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # 按查询内容分组统计
            hot_queries = self.session.query(
                QueryLog.query,
                func.count(QueryLog.id).label("count")
            ).filter(
                QueryLog.created_at >= start_date
            ).group_by(
                QueryLog.query
            ).order_by(
                desc("count")
            ).limit(limit).all()

            return [(q.query, q.count) for q in hot_queries]

        except Exception as e:
            logger.error(f"获取热门查询失败: {str(e)}")
            raise

    def get_user_query_count(
            self,
            user_id: str,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> int:
        """
        获取用户的查询次数

        参数：
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        返回：
            int: 查询次数
        """
        try:
            query = self.session.query(func.count(QueryLog.id)).filter(
                QueryLog.user_id == user_id
            )

            if start_date:
                query = query.filter(QueryLog.created_at >= start_date)
            if end_date:
                query = query.filter(QueryLog.created_at <= end_date)

            count = query.scalar()
            return count or 0

        except Exception as e:
            logger.error(f"获取用户查询次数失败: {str(e)}")
            raise

    def get_daily_query_trend(
            self,
            days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        获取每日查询趋势

        参数：
            days: 统计最近几天的数据

        返回：
            List[Dict]: 每日统计数据
        """
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # 按日期分组统计
            daily_stats = self.session.query(
                func.date(QueryLog.created_at).label("date"),
                func.count(QueryLog.id).label("count"),
                func.avg(QueryLog.total_time).label("avg_time"),
                func.avg(QueryLog.user_rating).label("avg_rating")
            ).filter(
                QueryLog.created_at >= start_date
            ).group_by(
                func.date(QueryLog.created_at)
            ).order_by(
                "date"
            ).all()

            result = []
            for stat in daily_stats:
                result.append({
                    "date": stat.date.isoformat(),
                    "count": stat.count,
                    "avg_time": float(stat.avg_time or 0),
                    "avg_rating": float(stat.avg_rating or 0)
                })

            return result

        except Exception as e:
            logger.error(f"获取每日查询趋势失败: {str(e)}")
            raise


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 创建Repository实例
from repository.query_log_repo import QueryLogRepository

repo = QueryLogRepository(session)


# 2. 记录查询日志
from core.constants import QueryType, RetrievalMode

log = repo.create_query_log(
    query="防水规范的标准是什么？",
    user_id="user_123",
    query_type=QueryType.STANDARD_QUERY,
    retrieval_mode=RetrievalMode.HYBRID,
    retrieved_count=5,
    retrieval_time=0.5,
    generation_time=1.2,
    total_time=1.7,
    answer="根据GB 50009-2012规范..."
)


# 3. 添加用户反馈
feedback = repo.create_feedback(
    query_log_id=log.id,
    rating=5,
    is_helpful=True,
    user_id="user_123",
    comment="答案非常准确，帮助很大！"
)


# 4. 获取统计信息
stats = repo.get_query_statistics()
print(f"总查询数: {stats['total_queries']}")
print(f"平均响应时间: {stats['avg_total_time']:.2f}s")
print(f"平均评分: {stats['avg_rating']:.1f}")


# 5. 获取热门查询
hot_queries = repo.get_hot_queries(limit=10, days=7)
for query, count in hot_queries:
    print(f"{query}: {count}次")


# 6. 获取每日趋势
trend = repo.get_daily_query_trend(days=30)
for day in trend:
    print(f"{day['date']}: {day['count']}次查询, 平均{day['avg_time']:.2f}s")
"""