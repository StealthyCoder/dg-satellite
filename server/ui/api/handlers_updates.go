// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear

package api

import (
	"net/http"

	"github.com/labstack/echo/v4"
)

type UpdateTufResp map[string]map[string]any

// @Summary Returns the TUF metadata for the update
// @Produce json
// @Success 200 {object} UpdateTufResp
// @Router  /updates/{prod}/{tag}/{update}/rollouts [get]
func (h handlers) updateGetTuf(c echo.Context) error {
	tag := c.Param("tag")
	update := c.Param("update")
	isProd := CtxGetIsProd(c.Request().Context())

	metas, err := h.storage.GetUpdateTufMetadata(tag, update, isProd)
	if err != nil {
		return EchoError(c, err, http.StatusInternalServerError, "failed to get update TUF metadata")
	}

	return c.JSON(http.StatusOK, metas)
}
