# -*- coding:utf-8 -*-

# ##### BEGIN LGPL LICENSE BLOCK #####
# GEOS - Geometry Engine Open Source
# http:#geos.osgeo.org
#
# Copyright (C) 2011 Sandro Santilli <strk@kbt.io>
# Copyright (C) 2005 2006 Refractions Research Inc.
# Copyright (C) 2001-2002 Vivid Solutions Inc.
# Copyright (C) 1995 Olivier Devillers <Olivier.Devillers@sophia.inria.fr>
#
# This is free software you can redistribute and/or modify it under
# the terms of the GNU Lesser General Public Licence as published
# by the Free Software Foundation.
# See the COPYING file for more information.
#
# ##### END LGPL LICENSE BLOCK #####

# <pep8 compliant>

# ----------------------------------------------------------
# Partial port (version 3.7.0) by: Stephen Leger (s-leger)
#
# ----------------------------------------------------------


from .algorithms import (
    PointLocator,
    LineIntersector,
    SimplePointInAreaLocator,
    IndexedPointInAreaLocator
    )
from .constants import (
    ComponentCoordinateExtracter,
    GeometryTypeId,
    Location
    )
from .noding import (
    SegmentStringUtil,
    SegmentIntersectionDetector,
    FastSegmentSetIntersectionFinder
    )


# operation/predicate


class RectangleContains():
    """
     * Optimized implementation of spatial predicate "contains"
     * for cases where the first Geometry is a rectangle.
     *
     * As a further optimization,
     * this class can be used directly to test many geometries against a single
     * rectangle.
     *
    """
    def __init__(self, rect):
        """
         * Create a new contains computer for two geometries.
         *
         * @param rect a rectangular geometry
        """
        self.rectangle = rect
        self.rectEnv = rect.envelope

    def isContainedInBoundary(self, geom) -> bool:

        # polygons can never be wholely contained in the boundary
        if geom.geometryTypeId == GeometryTypeId.GEOS_POLYGON:
            return False

        if geom.geometryTypeId == GeometryTypeId.GEOS_POINT:
            return self.isPointContainedInBoundary(geom)

        if geom.geometryTypeId == GeometryTypeId.GEOS_LINESTRING:
            return self.isLineStringContainedInBoundary(geom)

        for g in geom.geoms:
            if not self.isContainedInBoundary(g):
                return False

        return True

    def isCoordContainedInBoundary(self, coord) -> bool:
        """
         * contains = false iff the point is properly contained
         * in the rectangle.
         *
         * This code assumes that the point lies in the rectangle envelope
        """
        return (coord.x == self.rectEnv.minx or
            coord.x == self.rectEnv.maxx or
            coord.y == self.rectEnv.miny or
            coord.y == self.rectEnv.maxy)

    def isPointContainedInBoundary(self, geom) -> bool:
        """
         * Tests if a point is contained in the boundary of the target
         * rectangle.
         *
         * @param pt the point to test
         * @return true if the point is contained in the boundary
        """
        return self.isCoordContainedInBoundary(geom.coord)

    def isLineStringContainedInBoundary(self, geom) -> bool:
        """
         * Tests if a linestring is completely contained in the boundary
         * of the target rectangle.
         *
         * @param line the linestring to test
         * @return true if the linestring is contained in the boundary
        """
        coords = geom.coords
        for i in range(1, len(coords)):
            if not self.isLineSegmentContainedInBoundary(coords[i - 1], coords[i]):
                return False
        return True

    def isLineSegmentContainedInBoundary(self, p0, p1) -> bool:
        """
         * Tests if a line segment is contained in the boundary of the
         * target rectangle.
         *
         * @param p0 an endpoint of the segment
         * @param p1 an endpoint of the segment
         * @return true if the line segment is contained in the boundary
        """
        if p0 == p1:
            return self.isCoordContainedInBoundary(p0)

        if p0.x == p1.x:
            if (p0.x == self.rectEnv.minx or
                    p0.x == self.rectEnv.maxx):
                return True
        elif p0.y == p1.y:
            if (p0.y == self.rectEnv.miny or
                    p0.y == self.rectEnv.maxy):
                return True
        return False

    @staticmethod
    def contains(rect, geom) -> bool:
        rc = RectangleContains(rect)
        return rc._contains(geom)

    def _contains(self, geom) -> bool:

        if not self.rectEnv.contains(geom.envelope):
            return False

        # check that geom is not contained entirely in the rectangle boundary
        if self.isContainedInBoundary(geom):
            return False

        return True


# prepared


class PreparedGeometry():
    """
     * An interface for classes which prepare {@link Geometry}s
     * in order to optimize the performance
     * of repeated calls to specific geometric operations.
     *
     * A given implementation may provide optimized implementations
     * for only some of the specified methods,
     * and delegate the remaining methods to the original {@link Geometry} operations.
     * An implementation may also only optimize certain situations,
     * and delegate others.
     * See the implementing classes for documentation about which methods and situations
     * they optimize.
    """
    
    def contains(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} contains a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry contains the given Geometry
         *
         * @see Geometry#contains(Geometry)
        """
        raise NotImplementedError()

    def containsProperly(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} properly contains
         * a given geometry.
         *
         * The <code>containsProperly</code> predicate has the following
         * equivalent definitions:
         *
         * - Every point of the other geometry is a point of this
         *   geometry's interiors.
         * - The DE-9IM Intersection Matrix for the two geometries matches
         *   <code>[T**FF*FF*]</code>
         *
             * In other words, if the test geometry has any interaction with
         * the boundary of the target
             * geometry the result of <tt>containsProperly</tt> is <tt>false</tt>.
             * This is different semantics to the {@link Geometry::contains}
         * predicate, * in which test geometries can intersect the target's
         * boundary and still be contained.
         *
             * The advantage of using this predicate is that it can be computed
             * efficiently, since it avoids the need to compute the full
         * topological relationship of the input boundaries in cases where
         * they intersect.
         *
             * An example use case is computing the intersections
             * of a set of geometries with a large polygonal geometry.
             * Since <tt>intersection</tt> is a fairly slow operation, it can
         * be more efficient
             * to use <tt>containsProperly</tt> to filter out test geometries
         * which lie
             * wholly inside the area.  In these cases the intersection is
             * known <i>a priori</i> to be exactly the original test geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry properly contains the given Geometry
         *
         * @see Geometry::contains
        """
        raise NotImplementedError()

    def coveredBy(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} is covered by a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry is covered by the given Geometry
         *
         * @see Geometry#coveredBy(Geometry)
        """
        raise NotImplementedError()

    def covers(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} covers a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry covers the given Geometry
         *
         * @see Geometry#covers(Geometry)
        """
        raise NotImplementedError()

    def crosses(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} crosses a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry crosses the given Geometry
         *
         * @see Geometry#crosses(Geometry)
        """
        raise NotImplementedError()

    def disjoint(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} is disjoint from a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry is disjoint from the given Geometry
         *
         * @see Geometry#disjoint(Geometry)
        """
        raise NotImplementedError()

    def intersects(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} intersects a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry intersects the given Geometry
         *
         * @see Geometry#intersects(Geometry)
        """
        raise NotImplementedError()

    def overlaps(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} overlaps a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry overlaps the given Geometry
         *
         * @see Geometry#overlaps(Geometry)
        """
        raise NotImplementedError()

    def touches(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} touches a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry touches the given Geometry
         *
         * @see Geometry#touches(Geometry)
        """
        raise NotImplementedError()

    def within(self, geom) -> bool:
        """
         * Tests whether the base {@link Geometry} is within a given geometry.
         *
         * @param geom the Geometry to test
         * @return true if this Geometry is within the given Geometry
         *
         * @see Geometry#within(Geometry)
        """
        raise NotImplementedError()


class BasicPreparedGeometry(PreparedGeometry):
    """
     * A base class for {@link PreparedGeometry} subclasses.
     *
     * Contains default implementations for methods, which simply delegate
     * to the equivalent {@link Geometry} methods.
     * This class may be used as a "no-op" class for Geometry types
     * which do not have a corresponding {@link PreparedGeometry} implementation.
     *
     * @author Martin Davis
    """
    def __init__(self, geom):
        self.setGeometry(geom)

    def setGeometry(self, geom):
        self.geom = geom
        """
         * List of representative points for this geometry.
         * One vertex is included for every component of the geometry
         * (i.e. including one for every ring of polygonal geometries)
        """
        self.representativePts = []
        ComponentCoordinateExtracter.getCoordinates(geom, self.representativePts)

    def envelopesIntersect(self, geom) -> bool:
        """
         * Determines whether a Geometry g interacts with
         * this geometry by testing the geometry envelopes.
         *
         * @param g a Geometry
         * @return true if the envelopes intersect
        """
        return self.geom.envelope.intersects(geom.envelope)

    def envelopeCovers(self, geom) -> bool:
        return self.geom.envelope.covers(geom.envelope)

    def isAnyTargetComponentInTest(self, geom) -> bool:
        """
         * Tests whether any representative of the target geometry
         * intersects the test geometry.
         * This is useful in A/A, A/L, A/P, L/P, and P/P cases.
         *
         * @param geom the test geometry
         * @param repPts the representative points of the target geometry
         * @return true if any component intersects the areal test geometry
        """
        locator = PointLocator()
        for coord in self.representativePts:
            if locator.intersects(coord, geom):
                return True
        return False

    def contains(self, geom) -> bool:
        return self.geom.contains(geom)

    def containsProperly(self, geom) -> bool:
        # since raw relate is used, provide some optimizations
        if not self.geom.envelope.contains(geom.envelope):
            return False
        # otherwise, compute using relate mask
        return self.geom.relate(geom, "T**FF*FF*")

    def coveredBy(self, geom) -> bool:
        return self.geom.coveredBy(geom)

    def covers(self, geom) -> bool:
        return self.geom.covers(geom)

    def crosses(self, geom) -> bool:
        return self.geom.crosses(geom)

    def disjoint(self, geom) -> bool:
        """
         * Standard implementation for all geometries.
        """
        return not self.intersects(geom)

    def intersects(self, geom) -> bool:
        return self.geom.intersects(geom)

    def overlaps(self, geom) -> bool:
        return self.geom.overlaps(geom)

    def touches(self, geom) -> bool:
        return self.geom.touches(geom)

    def within(self, geom) -> bool:
        return self.geom.within(geom)


class PreparedPoint(BasicPreparedGeometry):
    """
     * A prepared version of {@link Point} or {@link MultiPoint} geometries.
     *
     * @author Martin Davis
    """
    def __init__(self, geom):
        BasicPreparedGeometry.__init__(self, geom)

    def intersects(self, geom) -> bool:
        """
         * Tests whether this point intersects a {@link Geometry}.
         *
         * The optimization here is that computing topology for the test
         * geometry is avoided. This can be significant for large geometries.
        """
        if not self.envelopesIntersect(geom):
            return False

        # This avoids computing topology for the test geometry
        return self.isAnyTargetComponentInTest(geom)


class PreparedLineString(BasicPreparedGeometry):
    """
     * A prepared version of {@link LinearRing}, {@link LineString} or {@link MultiLineString} geometries.
     *
     * @author mbdavis
     *
    """
    def __init__(self, geom):
        BasicPreparedGeometry.__init__(self, geom)
        # noding::FastSegmentSetIntersectionFinder
        self.segIntFinder = None

    def getIntersectionFinder(self):
        if self.segIntFinder is None:
            segStrings = [] 
            SegmentStringUtil.extractSegmentStrings(self.geom, segStrings)
            self.segIntFinder = FastSegmentSetIntersectionFinder(segStrings)
        return self.segIntFinder

    def intersects(self, geom) -> bool:
        if not self.envelopesIntersect(geom):
            return False
        return PreparedLineStringIntersects.intersects(self, geom)


class PreparedLineStringIntersects():
    """
     * Computes the <tt>intersects</tt> spatial relationship predicate
     * for a target {@link PreparedLineString} relative to all other
     * {@link Geometry} classes.
     *
     * Uses short-circuit tests and indexing to improve performance.
     *
     * @author Martin Davis
     *
    """
    def __init__(self, prep):
        self.prepLine = prep

    @staticmethod
    def intersects(prep, geom) -> bool:
        """
         * Computes the intersects predicate between a {@link PreparedLineString}
         * and a {@link Geometry}.
         *
         * @param prep the prepared linestring
         * @param geom a test geometry
         * @return true if the linestring intersects the geometry
        """
        op = PreparedLineStringIntersects(prep)
        return op._intersects(geom)

    def _intersects(self, geom) -> bool:
        """
         * Tests whether this geometry intersects a given geometry.
         *
         * @param geom the test geometry
         * @return true if the test geometry intersects
        """
        lineSegStr = []
        SegmentStringUtil.extractSegmentStrings(geom, lineSegStr)
        fssif = self.prepLine.getIntersectionFinder()
        # If any segments intersect, obviously intersects = true
        segsIntersect = fssif.intersects(lineSegStr)
        if segsIntersect:
            return True

        # For L/L case we are done
        if geom.dimension == 1:
            return False

        # For L/A case, need to check for proper inclusion of the target in the test
        if geom.dimension == 2 and self.prepLine.isAnyTargetComponentInTest(geom):
            return True

        # for L/P case, need to check if any points lie on line(s)
        if geom.dimension == 0:
            return self.isAnyTestPointInTarget(geom)

        return False

    def isAnyTestPointInTarget(self, geom) -> bool:
        """
         * Tests whether any representative point of the test Geometry intersects
         * the target geometry.
         * Only handles test geometries which are Puntal (dimension 0)
         *
         * @param geom a Puntal geometry to test
         * @return true if any point of the argument intersects the prepared geometry
        """
        locator = PointLocator()
        coords = []
        ComponentCoordinateExtracter.getCoordinates(geom, coords)

        for coord in coords:

            if locator.intersects(coord, self.prepLine.geom):
                return True

        return False


class PreparedPolygonPredicate():
    """
     * A base class for predicate operations on {@link PreparedPolygon}s.
     *
     * @author mbdavis
    """
    def __init__(self, prepPoly):
        # PreparedPolygon
        self.prepPoly = prepPoly

    def isAllTestComponentsInTarget(self, geom) -> bool:
        """
         * Tests whether all components of the test Geometry
         * are contained in the target geometry.
         *
         * Handles both linear and point components.
         *
         * @param geom a geometry to test
         * @return true if all components of the argument are contained
         *              in the target geometry
        """
        pts = []
        ComponentCoordinateExtracter.getCoordinates(geom, pts)
        for pt in pts:
            loc = self.prepPoly.getPointLocator().locate(pt)
            if loc == Location.EXTERIOR:
                return False
        return True

    def isAllTestComponentsInTargetInterior(self, geom) -> bool:
        """
         * Tests whether all components of the test Geometry
         * are contained in the interiors of the target geometry.
         *
         * Handles both linear and point components.
         *
         * @param geom a geometry to test
         * @return true if all componenta of the argument are contained in
         *              the target geometry interiors
        """
        pts = []
        ComponentCoordinateExtracter.getCoordinates(geom, pts)
        for pt in pts:
            loc = self.prepPoly.getPointLocator().locate(pt)
            if loc != Location.INTERIOR:
                return False
        return True

    def isAnyTestComponentInTarget(self, geom) -> bool:
        """
         * Tests whether any component of the test Geometry intersects
         * the area of the target geometry.
         *
         * Handles test geometries with both linear and point components.
         *
         * @param geom a geometry to test
         * @return true if any component of the argument intersects the
         *              prepared geometry
        """
        pts = []
        ComponentCoordinateExtracter.getCoordinates(geom, pts)
        for pt in pts:
            loc = self.prepPoly.getPointLocator().locate(pt)
            if loc != Location.EXTERIOR:
                return True
        return False

    def isAnyTestComponentInTargetInterior(self, geom) -> bool:
        """
         * Tests whether any component of the test Geometry intersects
         * the interiors of the target geometry.
         *
         * Handles test geometries with both linear and point components.
         *
         * @param geom a geometry to test
         * @return true if any component of the argument intersects the
         *              prepared area geometry interiors
        """
        pts = []
        ComponentCoordinateExtracter.getCoordinates(geom, pts)
        for pt in pts:
            loc = self.prepPoly.getPointLocator().locate(pt)
            if loc == Location.INTERIOR:
                return True
        return False

    def isAnyTargetComponentInAreaTest(self, geom, targetPts) -> bool:
        """
         * Tests whether any component of the target geometry
         * intersects the test geometry (which must be an areal geometry)
         *
         * @param geom the test geometry
         * @param repPts the representative points of the target geometry
         * @return true if any component intersects the areal test geometry
        """
        pts = []
        ComponentCoordinateExtracter.getCoordinates(geom, pts)
        for pt in pts:
            loc = SimplePointInAreaLocator.locate(pt, geom)
            if loc != Location.EXTERIOR:
                return True
        return False


class AbstractPreparedPolygonContains(PreparedPolygonPredicate):
    """
     * A base class containing the logic for computes the <tt>contains</tt>
     * and <tt>covers</tt> spatial relationship predicates
     * for a {@link PreparedPolygon} relative to all other {@link Geometry} classes.
     *
     * Uses short-circuit tests and indexing to improve performance.
     *
     * Contains and covers are very similar, and differ only in how certain
     * cases along the boundary are handled.  These cases require
     * full topological evaluation to handle, so all the code in
     * this class is common to both predicates.
     *
     * It is not possible to short-circuit in all cases, in particular
     * in the case where line segments of the test geometry touches the polygon
     * linework.
     * In this case full topology must be computed.
     * (However, if the test geometry consists of only points, this
     * <i>can</i> be evaluated in an optimized fashion.
     *
     * @author Martin Davis
    """
    def __init__(self, prepPoly, requireSomePointInInterior: bool=False):
        PreparedPolygonPredicate.__init__(self, prepPoly)
        self.hasSegmentIntersection = False
        self.hasProperIntersection = False
        self.hasNonProperIntersection = False
        """
         * This flag controls a difference between contains and covers.
         *
         * For contains the value is true.
         * For covers the value is false.
        """
        self.requireSomePointInInterior = requireSomePointInInterior

    def isProperIntersectionImpliesNotContainedSituation(self, geom) -> bool:

        # If the test geometry is polygonal we have the A/A situation.
        # In this case, a proper intersection indicates that
        # the Epsilon-Neighbourhood Exterior Intersection condition exists.
        # This condition means that in some small
        # area around the intersection point, there must exist a situation
        # where the interiors of the test intersects the exterior of the target.
        # This implies the test is NOT contained in the target.

        if (geom.geometryTypeId == GeometryTypeId.GEOS_MULTIPOLYGON or
                geom.geometryTypeId == GeometryTypeId.GEOS_POLYGON):
            return True

        # A single exterior with no interiors allows concluding that
        # a proper intersection implies not contained
        # (due to the Epsilon-Neighbourhood Exterior Intersection condition)

        if self.isSingleShell(self.prepPoly.geom):
            return True

        return False

    def isSingleShell(self, geom) -> bool:
        """
         * Tests whether a geometry consists of a single polygon with no interiors.
         *
         * @return true if the geometry is a single polygon with no interiors
        """
        # handles single-element MultiPolygons, as well as Polygons
        if geom.numgeoms != 1:
            return False

        poly = geom.getGeometryN(0)
        return len(poly.interiors) == 0

    def findAndClassifyIntersections(self, geom) -> None:
        # noding::SegmentString
        lineSegStr = []
        SegmentStringUtil.extractSegmentStrings(geom, lineSegStr)

        li = LineIntersector()
        intDetector = SegmentIntersectionDetector(li)

        self.prepPoly.getIntersectionFinder().intersects(lineSegStr, intDetector)

        self.hasSegmentIntersection = intDetector.hasIntersection
        self.hasProperIntersection = intDetector.hasProperIntersection
        self.hasNonProperIntersection = intDetector.hasNonProperIntersection

    def eval(self, geom) -> bool:
        """
         * Evaluate the <tt>contains</tt> or <tt>covers</tt> relationship
         * for the given geometry.
         *
         * @param geom the test geometry
         * @return true if the test geometry is contained
        """
        # Do point-in-poly tests first, since they are cheaper and may result
        # in a quick negative result.
        #
        # If a point of any test components does not lie in target,
        # result is false

        isAllInTargetArea = self.isAllTestComponentsInTarget(geom)
        if not isAllInTargetArea:
            return False

        # If the test geometry consists of only Points,
        # then it is now sufficient to test if any of those
        # points lie in the interiors of the target geometry.
        # If so, the test is contained.
        # If not, all points are on the boundary of the area,
        # which implies not contained.
        if self.requireSomePointInInterior and geom.dimension == 0:
            return self.isAnyTestComponentInTargetInterior(geom)

        # Check if there is any intersection between the line segments
        # in target and test.
        # In some important cases, finding a proper interesection implies that the
        # test geometry is NOT contained.
        # These cases are:
        # - If the test geometry is polygonal
        # - If the target geometry is a single polygon with no interiors
        # In both of these cases, a proper intersection implies that there
        # is some portion of the interiors of the test geometry lying outside
        # the target, which means that the test is not contained.
        properIntersectionImpliesNotContained = self.isProperIntersectionImpliesNotContainedSituation(geom)

        # find all intersection types which exist
        self.findAndClassifyIntersections(geom)

        if properIntersectionImpliesNotContained and self.hasProperIntersection:
            return False

        # If all intersections are proper
        # (i.e. no non-proper intersections occur)
        # we can conclude that the test geometry is not contained in the target area,
        # by the Epsilon-Neighbourhood Exterior Intersection condition.
        # In real-world data this is likely to be by far the most common situation,
        # since natural data is unlikely to have many exact vertex segment intersections.
        # Thus this check is very worthwhile, since it avoid having to perform
        # a full topological check.
        #
        # (If non-proper (vertex) intersections ARE found, this may indicate
        # a situation where two exteriors touch at a single vertex, which admits
        # the case where a line could cross between the exteriors and still be wholely contained in them.

        if self.hasSegmentIntersection and not self.hasNonProperIntersection:
            return False

        # If there is a segment intersection and the situation is not one
        # of the ones above, the only choice is to compute the full topological
        # relationship.  This is because contains/covers is very sensitive
        # to the situation along the boundary of the target.
        if self.hasSegmentIntersection:
            return self.fullTopologicalPredicate(geom)

        # This tests for the case where a ring of the target lies inside
        # a test polygon - which implies the exterior of the Target
        # intersects the interiors of the Test, and hence the result is false
        if (geom.geometryTypeId == GeometryTypeId.GEOS_MULTIPOLYGON or
                geom.geometryTypeId == GeometryTypeId.GEOS_POLYGON):
            isTargetInTestArea = self.isAnyTargetComponentInAreaTest(geom, self.prepPoly.representativePts)
            if isTargetInTestArea:
                return False
        return True

    def fullTopologicalPredicate(self, geom) -> bool:
        """
         * Computes the full topological predicate.
         * Used when short-circuit tests are not conclusive.
         *
         * @param geom the test geometry
         * @return true if this prepared polygon has the relationship with the test geometry
        """
        raise NotImplementedError()


class PreparedPolygon(BasicPreparedGeometry):
    """
     * A prepared version of {@link Polygon} or {@link MultiPolygon} geometries.
     *
     * @author mbdavis
     *
    """
    def __init__(self, geom):
        BasicPreparedGeometry.__init__(self, geom)

        self.is_rectangle = geom.is_rectangle

        # noding::FastSegmentSetIntersectionFinder
        self.segIntFinder = None

        # algorithm::locate::PointOnGeometryLocator
        self.ptOnGeomLoc = None


    def getIntersectionFinder(self):
        if self.segIntFinder is None:
            segStrings = []
            SegmentStringUtil.extractSegmentStrings(self.geom, segStrings)
            self.segIntFinder = FastSegmentSetIntersectionFinder(segStrings)
        return self.segIntFinder

    def getPointLocator(self):
        if self.ptOnGeomLoc is None:
            self.ptOnGeomLoc = IndexedPointInAreaLocator(self.geom)
        return self.ptOnGeomLoc

    def contains(self, geom) -> bool:

        if not self.envelopeCovers(geom):
            return False

        if self.is_rectangle:
            return RectangleContains.contains(self.geom, geom)

        return PreparedPolygonContains.contains(self, geom)

    def containsProperly(self, geom) -> bool:
        if not self.envelopeCovers(geom):
            return False

        return PreparedPolygonContainsProperly.containsProperly(self, geom)

    def covers(self, geom) -> bool:
        if not self.envelopeCovers(geom):
            return False

        return PreparedPolygonCovers.covers(self, geom)

    def intersects(self, geom) -> bool:
        if not self.envelopeCovers(geom):
            return False

        if self.is_rectangle:
            return RectangleContains.intersects(self.geom, geom)

        return PreparedPolygonIntersects.intersects(self, geom)


class PreparedPolygonIntersects(PreparedPolygonPredicate):
    """
     * Computes the <tt>intersects</tt> spatial relationship predicate
     * for {@link PreparedPolygon}s relative to all other {@link Geometry} classes.
     *
     * Uses short-circuit tests and indexing to improve performance.
     *
     * @author Martin Davis
     *
    """
    def __init__(self, prep):
        """
         * Creates an instance of this operation.
         *
         * @param prepPoly the PreparedPolygon to evaluate
        """
        PreparedPolygonPredicate.__init__(self, prep)

    @staticmethod
    def intersects(prep, geom) -> bool:
        """
         * Computes the intersects predicate between a {@link PreparedPolygon}
         * and a {@link Geometry}.
         *
         * @param prep the prepared polygon
         * @param geom a test geometry
         * @return true if the polygon intersects the geometry
        """
        polyInt = PreparedPolygonIntersects(prep)
        return polyInt._intersects(geom)

    def _intersects(self, geom) -> bool:
        """
         * Tests whether this PreparedPolygon intersects a given geometry.
         *
         * @param geom the test geometry
         * @return true if the test geometry intersects
        """
        isInPrepGeomArea = self.isAnyTestComponentInTarget(geom)

        if isInPrepGeomArea:
            return True

        if geom.geometryTypeId == GeometryTypeId.GEOS_POINT:
            return False

        # if any segment intersect, result is true
        # noding::SegmentString::ConstVect lineSegStr;
        lineSegStr = []
        SegmentStringUtil.extractSegmentStrings(geom, lineSegStr)

        segsIntersect = self.prepPoly.getIntersectionFinder().intersects(lineSegStr)
        if segsIntersect:
            return True

        if geom.dimension == 2:

            isPrepGeomInArea = self.isAnyTargetComponentInAreaTest(geom, self.prepPoly.representativePts)
            if isPrepGeomInArea:
                return True

        return False


class PreparedPolygonCovers(AbstractPreparedPolygonContains):
    """
     * Computes the <tt>covers</tt> spatial relationship predicate
     * for a {@link PreparedPolygon} relative to all other {@link Geometry} classes.
     *
     * Uses short-circuit tests and indexing to improve performance.
     *
     * It is not possible to short-circuit in all cases, in particular
     * in the case where the test geometry touches the polygon linework.
     * In this case full topology must be computed.
     *
     * @author Martin Davis
     *
    """
    def __init__(self, prep):
        PreparedPolygonPredicate.__init__(self, prep)

    def fullTopologicalPredicate(self, geom) -> bool:
        """
         * Computes the full topological <tt>covers</tt> predicate.
         * Used when short-circuit tests are not conclusive.
         *
         * @param geom the test geometry
         * @return true if this prepared polygon covers the test geometry
        """
        return self.prepPoly.geom.covers(geom)

    @staticmethod
    def covers(prep, geom) -> bool:
        """
         * Computes the </tt>covers</tt> predicate between a {@link PreparedPolygon}
         * and a {@link Geometry}.
         *
         * @param prep the prepared polygon
         * @param geom a test geometry
         * @return true if the polygon covers the geometry
        """
        polyInt = PreparedPolygonCovers(prep)
        return polyInt._covers(geom)

    def _covers(self, geom) -> bool:
        """
         * Tests whether this PreparedPolygon <tt>covers</tt> a given geometry.
         *
         * @param geom the test geometry
         * @return true if the test geometry is covered
        """
        return self.eval(geom)


class PreparedPolygonContains(AbstractPreparedPolygonContains):
    """
     * Computes the <tt>contains</tt> spatial relationship predicate
     * for a {@link PreparedPolygon} relative to all other {@link Geometry} classes.
     *
     * Uses short-circuit tests and indexing to improve performance.
     *
     * It is not possible to short-circuit in all cases, in particular
     * in the case where the test geometry touches the polygon linework.
     * In this case full topology must be computed.
     *
     * @author Martin Davis
    """
    def __init__(self, prep):
        """
         * Creates an instance of this operation.
         *
         * @param prepPoly the PreparedPolygon to evaluate
        """
        AbstractPreparedPolygonContains.__init__(self, prep)

    @staticmethod
    def contains(prep, geom) -> bool:
        """
         * Computes the </tt>contains</tt> predicate between a {@link PreparedPolygon}
         * and a {@link Geometry}.
         *
         * @param prep the prepared polygon
         * @param geom a test geometry
         * @return true if the polygon contains the geometry
        """
        polyInt = PreparedPolygonContains(prep)
        return polyInt._contains(geom)

    def _contains(self, geom) -> bool:
        """
         * Tests whether this PreparedPolygon <tt>contains</tt> a given geometry.
         *
         * @param geom the test geometry
         * @return true if the test geometry is contained
        """
        return self.eval(geom)

    def fullTopologicalPredicate(self, geom) -> bool:
        """
         * Computes the full topological <tt>contains</tt> predicate.
         * Used when short-circuit tests are not conclusive.
         *
         * @param geom the test geometry
         * @return true if this prepared polygon contains the test geometry
        """
        return self.prepPoly.geom.contains(geom)


class PreparedPolygonContainsProperly(PreparedPolygonPredicate):
    """
     * Computes the <tt>containsProperly</tt> spatial relationship predicate
     * for {@link PreparedPolygon}s relative to all other {@link Geometry} classes.
     *
     * Uses short-circuit tests and indexing to improve performance.
     *
     * A Geometry A <tt>containsProperly</tt> another Geometry B iff
     * all points of B are contained in the Interior of A.
     * Equivalently, B is contained in A AND B does not intersect
     * the Boundary of A.
     *
     * The advantage to using this predicate is that it can be computed
     * efficiently, with no need to compute topology at individual points.
     * In a situation with many geometries intersecting the boundary
     * of the target geometry, this can make a performance difference.
     *
     * @author Martin Davis
    """
    def __init__(self, prep):
        """
         * Creates an instance of this operation.
         *
         * @param prepPoly the PreparedPolygon to evaluate
        """
        AbstractPreparedPolygonContains.__init__(self, prep)

    @staticmethod
    def containsProperly(prep, geom) -> bool:
        """
         * Computes the </tt>containsProperly</tt> predicate between a {@link PreparedPolygon}
         * and a {@link Geometry}.
         *
         * @param prep the prepared polygon
         * @param geom a test geometry
         * @return true if the polygon properly contains the geometry
        """
        polyInt = PreparedPolygonContainsProperly(prep)
        return polyInt._containsProperly(geom)

    def _containsProperly(self, geom)-> bool:
        """
         * Tests whether this PreparedPolygon containsProperly a given geometry.
         *
         * @param geom the test geometry
         * @return true if the test geometry is contained properly
        """
        # Do point-in-poly tests first, since they are cheaper and may result
        # in a quick negative result.
        # If a point of any test components does not lie in target,
        # result is false
        isAllInPrepGeomArea = self.isAllTestComponentsInTargetInterior(geom)
        if not isAllInPrepGeomArea:
            return False

        # If any segments intersect, result is false
        # noding::SegmentString::ConstVect
        lineSegStr = []
        SegmentStringUtil.extractSegmentStrings(geom, lineSegStr)
        segsIntersect = self.prepPoly.getIntersectionFinder().intersects(lineSegStr)

        if segsIntersect:
            return False

        """
         * Given that no segments intersect, if any vertex of the target
         * is contained in some test component.
         * the test is NOT properly contained.
         """
        if (geom.geometryTypeId == GeometryTypeId.GEOS_MULTIPOLYGON or
                geom.geometryTypeId == GeometryTypeId.GEOS_POLYGON):
            # TODO: generalize this to handle GeometryCollections

            isTargetGeomInTestArea = self.isAnyTargetComponentInAreaTest(geom, self.prepPoly.representativePts)
            if isTargetGeomInTestArea:
                return False

        return True


class PreparedGeometryFactory():
    """
     * A factory for creating {@link PreparedGeometry}s.
     *
     * It chooses an appropriate implementation of PreparedGeometry
     * based on the geoemtric type of the input geometry.
     * In the future, the factory may accept hints that indicate
     * special optimizations which can be performed.
     *
     * @author Martin Davis
     *
    """

    @staticmethod
    def prepare(geom):
        """
         * Creates a new {@link PreparedGeometry} appropriate for the argument {@link Geometry}.
         *
         * @param geom the geometry to prepare
         * @return the prepared geometry
        """
        pf = PreparedGeometryFactory()
        return pf.create(geom)
    
    @staticmethod
    def prep(geom):    
        return PreparedGeometryFactory.prepare(geom)
        
    def create(self, geom):
        """
         * Creates a new {@link PreparedGeometry} appropriate for the argument {@link Geometry}.
         *
         * @param geom the geometry to prepare
         * @return the prepared geometry
        """
        tid = geom.geometryTypeId

        if tid in [
                GeometryTypeId.GEOS_MULTIPOINT,
                GeometryTypeId.GEOS_POINT
                ]:
            return PreparedPoint(geom)

        if tid in [
                GeometryTypeId.GEOS_LINEARRING,
                GeometryTypeId.GEOS_LINESTRING,
                GeometryTypeId.GEOS_MULTILINESTRING
                ]:
            return PreparedLineString(geom)

        if tid in [
                GeometryTypeId.GEOS_POLYGON,
                GeometryTypeId.GEOS_MULTIPOLYGON
                ]:
            return PreparedPolygon(geom)

        return BasicPreparedGeometry(geom)
