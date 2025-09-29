// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear

package api

import (
	"net/http"

	"github.com/foundriesio/dg-satellite/server"
	"github.com/foundriesio/dg-satellite/storage/api"
	"github.com/labstack/echo/v4"
)

type Device = api.Device

// @Summary Get a device by its UUID
// @Produce json
// @Success 200 Device
// @Router  /devices/:uuid [get]
func (h *handlers) deviceGet(c echo.Context) error {
	uuid := c.Param("uuid")

	device, err := h.storage.DeviceGet(uuid)
	if err != nil {
		return server.EchoError(c, err, http.StatusInternalServerError, "Failed to lookup device")
	}

	if device == nil {
		return echo.NewHTTPError(http.StatusNotFound, "Not found")
	}
	return c.JSON(http.StatusOK, device)
}
