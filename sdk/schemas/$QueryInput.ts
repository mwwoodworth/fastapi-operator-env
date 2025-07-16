/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $QueryInput = {
    properties: {
        query: {
            type: 'string',
            isRequired: true,
        },
        project_id: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
        top_k: {
            type: 'number',
        },
    },
} as const;
