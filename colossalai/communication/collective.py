#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import torch
import torch.distributed as dist
from torch.distributed import ReduceOp
from torch import Tensor

from colossalai.context import ParallelMode
from colossalai.core import global_context as gpc
from colossalai.utils import get_current_device


def all_gather(tensor: Tensor, dim: int, parallel_mode: ParallelMode, async_op: bool = False) -> Tensor:
    """Gathers all tensors from the parallel group and concatenates them in a 
    specific dimension.
    
    :param tensor: Tensor to be gathered
    :param dim: The dimension concatenating in
    :param parallel_mode: Parallel group mode used in this communication
    :type tensor: :class:`torch.Tensor`
    :type dim: int
    :type parallel_mode: :class:`colossalai.context.ParallelMode`
    :return: The tensor generated by all-gather
    :rtype: :class:`torch.Tensor`
    """
    depth = gpc.get_world_size(parallel_mode)
    if depth == 1:
        out = [tensor]
        work = None
    else:
        shape = list(tensor.shape)
        shape[0], shape[dim] = shape[dim], shape[0]
        shape[0] *= depth
        out = torch.empty(shape, dtype=tensor.dtype, device=get_current_device())
        temp = list(torch.chunk(out, depth, dim=0))
        work = dist.all_gather(tensor_list=temp,
                               tensor=tensor.transpose(0, dim).contiguous(),
                               group=gpc.get_group(parallel_mode),
                               async_op=async_op)
        out = torch.transpose(out, 0, dim)
    if async_op:
        return out, work
    else:
        return out


def reduce_scatter(tensor: Tensor,
                   dim: int,
                   parallel_mode: ParallelMode,
                   op: ReduceOp = ReduceOp.SUM,
                   async_op: bool = False) -> Tensor:
    """Reduces all tensors then scatters it in a specific dimension to all 
    members in the parallel group.
    
    :param tensor: Tensor to be reduced and scattered
    :param dim: The dimension scattering in
    :param parallel_mode: Parallel group mode used in this communication
    :type tensor: :class:`torch.Tensor`
    :type dim: int
    :type parallel_mode: :class:`colossalai.context.ParallelMode`
    :return: The tensor generated by reduce-scatter
    :rtype: :class:`Tensor`
    """
    depth = gpc.get_world_size(parallel_mode)
    if depth == 1:
        out = tensor
        work = None
    else:
        temp = list(map(lambda x: x.contiguous(), torch.chunk(tensor, depth, dim=dim)))
        out = torch.empty(temp[0].shape, dtype=tensor.dtype, device=get_current_device())
        work = dist.reduce_scatter(output=out,
                                   input_list=temp,
                                   op=op,
                                   group=gpc.get_group(parallel_mode),
                                   async_op=async_op)
    if async_op:
        return out, work
    else:
        return out


def all_reduce(tensor: Tensor,
               parallel_mode: ParallelMode,
               op: ReduceOp = ReduceOp.SUM,
               async_op: bool = False) -> Tensor:
    depth = gpc.get_world_size(parallel_mode)
    if depth == 1:
        work = None
    else:
        work = dist.all_reduce(tensor.contiguous(), op=op, group=gpc.get_group(parallel_mode), async_op=async_op)
    if async_op:
        return tensor, work
    else:
        return tensor


def broadcast(tensor: Tensor, src: int, parallel_mode: ParallelMode, async_op: bool = False):
    depth = gpc.get_world_size(parallel_mode)
    if depth == 1:
        work = None
    else:
        work = dist.broadcast(tensor.contiguous(), src=src, group=gpc.get_group(parallel_mode), async_op=async_op)
    if async_op:
        return tensor, work
    else:
        return tensor


def reduce(tensor: Tensor, dst: int, parallel_mode: ParallelMode, op: ReduceOp = ReduceOp.SUM, async_op: bool = False):
    depth = gpc.get_world_size(parallel_mode)
    if depth == 1:
        work = None
    else:
        work = dist.reduce(tensor.contiguous(), dst=dst, op=op, group=gpc.get_group(parallel_mode), async_op=async_op)
    if async_op:
        return tensor, work
    else:
        return tensor