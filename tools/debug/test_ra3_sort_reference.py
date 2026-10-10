"""Extract the current sorter for an isolated MSVC test; no OpenGL/image claims.

Run with Python and an output directory, then compile ra3_sort_reference.cpp with
the repository's required vcvars64/VSLANG environment. Uses the real sorter body
and a minimal vector/display-array adapter, not engine storage or matrix code.
"""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
source = (root / 'source/source/gameengine/Rasterizer/RAS_DisplayArray.cpp').read_text()
polygon = source[source.index('struct PolygonSort {'):source.index('RAS_DisplayArray::RAS_DisplayArray(')]
sorter = source[source.index('void RAS_DisplayArray::SortPolygons('):source.index('RAS_DisplayArray::PrimitiveType RAS_DisplayArray::GetPrimitiveType()')]
storage_source = (root / 'source/source/gameengine/Rasterizer/RAS_DisplayArrayStorage.cpp').read_text()
cache = storage_source[storage_source.index('void RAS_DisplayArrayStorage::SortPolygons('):storage_source.index('void RAS_DisplayArrayStorage::IndexPrimitives()')]
adapter = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <iostream>
#include <random>
#include <vector>
namespace mt {
struct vec3 {
    float x, y, z;
    vec3(float a=0, float b=0, float c=0): x(a), y(b), z(c) {}
    vec3& operator+=(const vec3& b) { x+=b.x; y+=b.y; z+=b.z; return *this; }
};
const vec3 zero3;
float dot(const vec3& a, const vec3& b) { return a.x*b.x+a.y*b.y+a.z*b.z; }
using mat3x4 = std::array<float, 12>;
}
struct RAS_DisplayArray;
struct RAS_DisplayArrayStorage {
    bool m_polygonOrderValid=false, mapFail=false, unmapFail=false;
    float m_polygonDirection[3]={};
    std::vector<unsigned int> buffer;
    unsigned int maps=0;
    void InvalidatePolygonOrder() { m_polygonOrderValid=false; }
    unsigned int* GetIndexMap() { InvalidatePolygonOrder(); ++maps; return mapFail?nullptr:buffer.data(); }
    bool FlushIndexMap() { return !unmapFail; }
    void SortPolygons(RAS_DisplayArray*,const mt::mat3x4&);
};
struct RAS_DisplayArray {
    enum { TRIANGLES, LINES, POINTS };
    int m_type=TRIANGLES;
    struct { std::vector<mt::vec3> positions; } m_vertexData;
    std::vector<unsigned int> m_primitiveIndices;
    std::vector<mt::vec3> m_polygonCenters;
    RAS_DisplayArrayStorage m_storage;
    unsigned int GetPrimitiveIndexCount() const { return (unsigned int)m_primitiveIndices.size(); }
    int GetPrimitiveType() const { return m_type; }
    void SortPolygons(const mt::mat3x4&, unsigned int*);
    void InvalidatePolygonCenters();
};
'''
tests = r'''
int main() {
    std::mt19937 rng(314159);
    std::uniform_real_distribution<float> sample(-20,20);
    unsigned int draws=0;
    for (int trial=0; trial<400; ++trial) {
        RAS_DisplayArray a;
        const unsigned int count=2+rng()%100;
        for (unsigned int i=0; i<count*3; ++i) {
            a.m_vertexData.positions.emplace_back(sample(rng),sample(rng),sample(rng));
            a.m_primitiveIndices.push_back(i);
        }
        std::vector<unsigned int> output(count*3), previous;
        for (int pass=0; pass<12; ++pass) {
            mt::mat3x4 view{};
            view[2]=sample(rng); view[5]=sample(rng); view[8]=sample(rng);
            a.SortPolygons(view, output.data());
            ++draws;
            std::vector<unsigned int> seen(count,0);
            float last=-INFINITY;
            for (unsigned int i=0; i<count; ++i) {
                unsigned int first=output[i*3];
                assert(first%3==0 && first<count*3);
                assert(output[i*3+1]==first+1 && output[i*3+2]==first+2);
                assert(++seen[first/3]==1);
                mt::vec3 center;
                for (int j=0;j<3;++j) center+=a.m_vertexData.positions[first+j];
                const float depth=mt::dot(mt::vec3(view[2],view[5],view[8]),center);
                assert(depth>=last); last=depth;
            }
            previous=output;
            view[9]=sample(rng); view[10]=sample(rng); view[11]=sample(rng);
            a.SortPolygons(view, output.data()); ++draws;
            assert(previous==output); // Translation must not alter this sorter.
            for (auto& p:a.m_vertexData.positions) p.z+=sample(rng);
            a.InvalidatePolygonCenters();
        }
    }
    // Equal depths: require repeatability, not a new tie-breaking convention.
    RAS_DisplayArray equal;
    for (unsigned int i=0;i<90;++i) {
        equal.m_primitiveIndices.push_back(i);
        equal.m_vertexData.positions.emplace_back((float)i,0,1);
    }
    mt::mat3x4 view{}; view[8]=1;
    std::vector<unsigned int> first(90), second(90);
    equal.SortPolygons(view,first.data()); equal.SortPolygons(view,second.data());
    assert(first==second);
    equal.SortPolygons(view,nullptr);
    equal.m_type=RAS_DisplayArray::LINES;
    std::fill(second.begin(),second.end(),999);
    equal.SortPolygons(view,second.data());
    assert(std::all_of(second.begin(),second.end(),[](unsigned int i){return i==999;}));
    RAS_DisplayArray a;
    for(unsigned int i=0;i<90;++i) {
        a.m_primitiveIndices.push_back(i);
        a.m_vertexData.positions.emplace_back(sample(rng),sample(rng),sample(rng));
    }
    auto& storage=a.m_storage;
    storage.buffer.resize(90);
    std::vector<unsigned int> expected(90);
    auto compare=[&](const mt::mat3x4& matrix) {
        a.SortPolygons(matrix,expected.data());
        storage.SortPolygons(&a,matrix);
        assert(storage.buffer==expected);
    };
    view={};view[8]=1;
    compare(view);
    for(int i=0;i<1000;++i) compare(view);
    assert(storage.maps==1); // Repeated direction avoids map and sort.
    for(int i=0;i<1000;++i) {
        view[8]=(i%2)?1.0f:-1.0f; compare(view); // Shared slots/camera alternation.
    }
    unsigned int previousMaps=storage.maps;
    a.m_vertexData.positions[0].z+=100;
    a.InvalidatePolygonCenters(); compare(view);
    assert(storage.maps==previousMaps+1);
    std::reverse(a.m_primitiveIndices.begin(),a.m_primitiveIndices.end());
    a.InvalidatePolygonCenters(); compare(view); // Same-size topology change.
    storage.InvalidatePolygonOrder(); compare(view); // Recreated/overwritten IBO.
    storage.mapFail=true; storage.InvalidatePolygonOrder();
    storage.SortPolygons(&a,view); assert(!storage.m_polygonOrderValid);
    storage.mapFail=false; compare(view);
    storage.unmapFail=true; storage.InvalidatePolygonOrder();
    storage.SortPolygons(&a,view); assert(!storage.m_polygonOrderValid);
    storage.unmapFail=false; previousMaps=storage.maps; compare(view);
    assert(storage.maps==previousMaps+1);
    RAS_DisplayArrayStorage copiedStorage;
    assert(!copiedStorage.m_polygonOrderValid);
    std::cout << "PASS baseline draws=" << draws << " cache differential=2005+ failure/retry maps=" << storage.maps << "\n";
}
'''
destination = Path(sys.argv[1])
destination.mkdir(parents=True, exist_ok=True)
(destination / 'ra3_sort_reference.cpp').write_text(adapter + polygon + sorter + cache + tests)
print(destination / 'ra3_sort_reference.cpp')
