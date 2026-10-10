#include "RAS_DisplayArrayStorage.h"
#include "RAS_StorageVbo.h"
#include "RAS_Rasterizer.h"
#include "RAS_DisplayArray.h"

RAS_DisplayArrayStorage::RAS_DisplayArrayStorage()
{
}

RAS_DisplayArrayStorage::~RAS_DisplayArrayStorage()
{
}

void RAS_DisplayArrayStorage::Construct(RAS_DisplayArray *array)
{
	InvalidatePolygonOrder();
	m_vbo.reset(new RAS_StorageVbo(array));
}

RAS_StorageVbo *RAS_DisplayArrayStorage::GetVbo() const
{
	return m_vbo.get();
}

void RAS_DisplayArrayStorage::UpdateVertexData(unsigned int modifiedFlag)
{
	if (modifiedFlag & RAS_DisplayArray::POSITION_MODIFIED) {
		InvalidatePolygonOrder();
	}
	m_vbo->UpdateVertexData(modifiedFlag);
}

void RAS_DisplayArrayStorage::UpdateSize()
{
	// RAS_StorageVbo::UpdateSize invalidates polygon centers and this order.
	m_vbo->UpdateSize();
}

unsigned int *RAS_DisplayArrayStorage::GetIndexMap()
{
	InvalidatePolygonOrder();
	return m_vbo->GetIndexMap();
}

bool RAS_DisplayArrayStorage::FlushIndexMap()
{
	return m_vbo->FlushIndexMap();
}

void RAS_DisplayArrayStorage::InvalidatePolygonOrder()
{
	m_polygonOrderValid = false;
}

void RAS_DisplayArrayStorage::SortPolygons(RAS_DisplayArray *array, const mt::mat3x4& transform)
{
	if (array->GetPrimitiveIndexCount() <= 3 ||
			array->GetPrimitiveType() != RAS_DisplayArray::TRIANGLES) {
		return;
	}
	const float direction[3] = {transform[2], transform[5], transform[8]};
	if (m_polygonOrderValid && direction[0] == m_polygonDirection[0] &&
			direction[1] == m_polygonDirection[1] && direction[2] == m_polygonDirection[2]) {
		return;
	}
	unsigned int *indices = GetIndexMap();
	if (!indices) {
		return;
	}
	array->SortPolygons(transform, indices);
	if (FlushIndexMap()) {
		std::copy(direction, direction + 3, m_polygonDirection);
		m_polygonOrderValid = true;
	}
}

void RAS_DisplayArrayStorage::IndexPrimitives()
{
	m_vbo->IndexPrimitives();
	RAS_Rasterizer::IncDrawCallCount();
}

void RAS_DisplayArrayStorage::IndexPrimitivesInstancing(unsigned int numslots)
{
	m_vbo->IndexPrimitivesInstancing(numslots);
	RAS_Rasterizer::IncDrawCallCount();
}

void RAS_DisplayArrayStorage::IndexPrimitivesBatching(const std::vector<intptr_t>& indices, const std::vector<int>& counts)
{
	m_vbo->IndexPrimitivesBatching(indices, counts);
	RAS_Rasterizer::IncDrawCallCount();
}
