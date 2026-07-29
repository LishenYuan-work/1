"""评论路由：发表、列表、回复、删除"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import Comment, Profile, Debate
from app.dependencies import get_current_user, require_user
from app.models.schemas import CreateCommentRequest, CommentItem

router = APIRouter(prefix="/api/debates/{debate_id}/comments", tags=["comments"])


def _build_comment_tree(comments: list[Comment]) -> list[CommentItem]:
    """将扁平评论列表构建为树形结构"""
    items = {
        c.id: CommentItem(
            id=c.id,
            debate_id=c.debate_id,
            user_id=c.user_id,
            username=c.user.display_name if c.user else "匿名",
            content=c.content,
            parent_id=c.parent_id,
            replies=[],
            created_at=str(c.created_at),
        )
        for c in comments
    }
    roots = []
    for c in comments:
        item = items[c.id]
        if c.parent_id and c.parent_id in items:
            items[c.parent_id].replies.append(item)
        else:
            roots.append(item)
    return roots


# ========== 发表评论 ==========

@router.post("", response_model=CommentItem, status_code=201)
async def create_comment(
    debate_id: str,
    req: CreateCommentRequest,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_user),
):
    """发表评论"""
    # 验证辩论存在
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "辩论不存在")

    # 如果是回复，验证父评论存在且属于同一辩论
    if req.parent_id:
        parent_result = await db.execute(select(Comment).where(Comment.id == req.parent_id))
        parent = parent_result.scalar_one_or_none()
        if not parent or parent.debate_id != debate_id:
            raise HTTPException(400, "回复的评论不存在")

    comment = Comment(
        debate_id=debate_id,
        user_id=user.id,
        content=req.content,
        parent_id=req.parent_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    # 加载用户信息
    await db.refresh(comment, ["user"])

    return CommentItem(
        id=comment.id,
        debate_id=comment.debate_id,
        user_id=comment.user_id,
        username=user.display_name,
        content=comment.content,
        parent_id=comment.parent_id,
        replies=[],
        created_at=str(comment.created_at),
    )


# ========== 评论列表 ==========

def _comment_to_item(c: Comment) -> CommentItem:
    """递归转换 Comment ORM 对象为 Pydantic 模型"""
    return CommentItem(
        id=c.id,
        debate_id=c.debate_id,
        user_id=c.user_id,
        username=c.user.display_name if c.user else "匿名",
        content=c.content,
        parent_id=c.parent_id,
        replies=[_comment_to_item(r) for r in (c.replies or [])],
        created_at=str(c.created_at),
    )


@router.get("", response_model=list[CommentItem])
async def list_comments(debate_id: str, db: AsyncSession = Depends(get_db)):
    """获取辩论的所有评论（树形结构）"""
    result = await db.execute(
        select(Comment)
        .options(
            selectinload(Comment.user),
            selectinload(Comment.replies).selectinload(Comment.user),
            selectinload(Comment.replies).selectinload(Comment.replies),
        )
        .where(Comment.debate_id == debate_id, Comment.parent_id == None)
        .order_by(Comment.created_at)
    )
    comments = result.unique().scalars().all()
    return [_comment_to_item(c) for c in comments]


# ========== 删除评论 ==========

@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    debate_id: str,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user: Profile = Depends(require_user),
):
    """删除评论（仅作者可删）"""
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "评论不存在")
    if comment.user_id != user.id:
        raise HTTPException(403, "只能删除自己的评论")

    await db.delete(comment)
    await db.commit()
