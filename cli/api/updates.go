// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear

package api

type UpdatesApi struct {
	api  *Api
	Type string
}

// Updates returns an UpdatesApi instance for either "ci" or "prod" updates.
func (a *Api) Updates(updateType string) UpdatesApi {
	return UpdatesApi{
		api:  a,
		Type: updateType,
	}
}

func (u UpdatesApi) List() (map[string][]string, error) {
	var updates map[string][]string
	return updates, u.api.Get("/v1/updates/"+u.Type, &updates)
}

func (u UpdatesApi) Get(tag, updateName string) ([]string, error) {
	var rollouts []string
	endpoint := "/v1/updates/" + u.Type + "/" + tag + "/" + updateName + "/rollouts"
	return rollouts, u.api.Get(endpoint, &rollouts)
}
